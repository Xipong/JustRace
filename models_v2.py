from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple, Callable
import random, json

from config_v2 import (
    USE_ROLLING_RESISTANCE, C_RR, K_LAT, ERROR_RATE_BASE, TIME_PENALTY_RANGE, DT_MAX,
    XP_PER_KM, PROGRESSION
)

MAJOR_MISTAKES = True
MAJOR_MISTAKE_RATE = 0.0003
MAJOR_PENALTY_RANGE = (1.2, 3.0)

@dataclass
class Car:
    id: str
    name: str
    power: float   # kW
    mass: float    # kg
    cd: float
    area: float    # m^2
    tire_grip: float

    @property
    def power_watts(self) -> float:
        return self.power * 1000.0

    @property
    def vmax_power_limited(self) -> float:
        rho = 1.225
        denom = 0.5 * self.cd * rho * self.area
        return (self.power_watts / max(denom, 1e-9)) ** (1.0 / 3.0)

@dataclass
class TrackSegment:
    name: str
    type: str      # "straight" | "corner"
    length: float
    entry_complexity: float
    exit_complexity: float
    accel_coef: float
    brake_coef: float

class Track:
    def __init__(self, track_id: str, name: str, segments: List[TrackSegment]):
        self.id = track_id
        self.name = name
        self.segments = segments
        self.total_length = sum(s.length for s in segments)

@dataclass
class DriverProfile:
    id: str
    name: str
    braking: float
    consistency: float
    stress: float
    throttle: float
    cornering: float
    starts: float
    xp: float = 0.0

    @staticmethod
    def default(id: str, name: str) -> "DriverProfile":
        return DriverProfile(id=id, name=name,
                             braking=70, consistency=70, stress=70,
                             throttle=70, cornering=70, starts=70)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(s: str) -> "DriverProfile":
        return DriverProfile(**json.loads(s))

    def update_after_race(self, km_driven: float, incidents: int, clean_corners: int) -> Dict[str, float]:
        gains: Dict[str, float] = {}
        self.xp += km_driven * XP_PER_KM
        total_segments = max(1, clean_corners + incidents)
        clean_ratio = clean_corners / total_segments
        perf = 0.7 + 0.6 * clean_ratio

        def improve(skill_name: str, current: float):
            prog_key = skill_name if skill_name in PROGRESSION else "consistency"
            p = PROGRESSION[prog_key]
            eta, target = p["eta"], p["target"]
            delta = eta * (1.0 - current / target) * (0.25 + 0.75 * perf)
            delta = max(0.05, min(delta, 1.2))
            new_val = min(100.0, current + delta)
            return new_val, round(new_val - current, 2)

        for skill in ["braking", "consistency", "stress", "throttle", "cornering", "starts"]:
            cur = getattr(self, skill)
            new_val, gain = improve(skill, cur)
            setattr(self, skill, new_val)
            gains[skill] = gain
        return gains

class RaceState:
    def __init__(self):
        self.current_lap = 1
        self.current_segment_idx = 0
        self.speed = 1.0
        self.segment_distance = 0.0
        self.total_time = 0.0
        self.is_finished = False
        self.incidents = 0
        self.clean_corners = 0
        self.penalties: List[Dict] = []

class RaceEngine:
    def __init__(self, car: Car, track: Track, laps: int,
                 driver: Optional[DriverProfile] = None,
                 use_rr: bool = USE_ROLLING_RESISTANCE, c_rr: float = C_RR, k_lat: float = K_LAT,
                 seed: Optional[int] = 42,
                 on_event: Optional[Callable[[Dict], None]] = None):
        self.car = car
        self.track = track
        self.laps = laps
        self.state = RaceState()
        self.driver = driver or DriverProfile.default("anon", "Anon")
        self.use_rr = use_rr
        self.c_rr = c_rr if use_rr else 0.0
        self.k_lat = k_lat
        self.rho = 1.225
        self.random = random.Random(seed)
        self.on_event = on_event
        # Время последнего события сегмента. Нужен для регулярных "тиков"
        # чтобы не зависеть от длины сегмента и не спамить сообщениями.
        self._last_seg_evt_time = 0.0

    @property
    def current_segment(self) -> TrackSegment:
        return self.track.segments[self.state.current_segment_idx]

    def _notify(self, evt: Dict):
        if self.on_event:
            try:
                self.on_event(evt)
            except Exception:
                pass

    def _maybe_error(self, lam: float, in_corner: bool, seg_name: str) -> bool:
        base = ERROR_RATE_BASE * (1.5 if in_corner else 1.0)
        p = min(0.9, base * lam)
        if self.random.random() < p:
            from random import uniform
            dt = uniform(*TIME_PENALTY_RANGE)
            self.state.total_time += dt
            self.state.penalties.append({"type": "minor", "delta_s": dt, "segment": seg_name, "load": lam})
            self.state.incidents += 1
            self._notify({
                "type": "penalty",
                "severity": "minor",
                "delta_s": dt,
                "segment": seg_name,
                "load": lam,
                "time_s": self.state.total_time,
            })
            return True
        if MAJOR_MISTAKES and (self.random.random() < MAJOR_MISTAKE_RATE):
            from random import uniform
            dt = uniform(*MAJOR_PENALTY_RANGE)
            self.state.total_time += dt
            self.state.penalties.append({"type": "major", "delta_s": dt, "segment": seg_name, "load": lam})
            self.state.incidents += 1
            self._notify({
                "type": "penalty",
                "severity": "major",
                "delta_s": dt,
                "segment": seg_name,
                "load": lam,
                "time_s": self.state.total_time,
            })
            return True
        return False

    def _step_straight(self, seg: TrackSegment, dt: float):
        v = max(self.state.speed, 1.0)
        drag_power = 0.5 * self.car.cd * self.rho * self.car.area * v ** 3
        a_power = (self.car.power_watts - drag_power) / (self.car.mass * v)
        a_tire = 9.81 * self.car.tire_grip
        a_long_max = min(a_power, a_tire)
        if self.use_rr:
            a_long_max -= 9.81 * self.c_rr
        lam = 0.5 * (seg.entry_complexity + seg.exit_complexity)
        lam_factor = max(0.08, 1.0 - 0.11 * lam)
        a_eff = min(a_long_max * seg.accel_coef * lam_factor, a_long_max)
        self.state.speed = max(self.state.speed + a_eff * dt, 0.1)
        self.state.segment_distance += self.state.speed * dt
        self.state.total_time += dt

    def _step_corner(self, seg: TrackSegment, dt: float):
        v_in = max(self.state.speed, 0.1)
        lam = max(0.1, 0.5 * (seg.entry_complexity + seg.exit_complexity))
        v_factor = max(0.1, 1.0 - 0.10 * lam)
        v_target = self.car.vmax_power_limited * v_factor
        v_target = max(12.0, min(v_target, 120.0))
        a_long_max = 0.8 * 9.81 * self.car.tire_grip
        a_eff = (v_target - v_in) / max(dt, 1e-3)
        a_eff = max(min(a_eff, a_long_max), -a_long_max)
        if self.state.speed > v_target:
            a_eff = min(a_eff, -a_long_max)
        self.state.speed = max(self.state.speed + a_eff * dt, 0.1)
        self.state.segment_distance += self.state.speed * dt
        self.state.total_time += dt
        made_error = self._maybe_error(lam, in_corner=True, seg_name=seg.name)
        if not made_error:
            self.state.clean_corners += 1

    def step(self, dt: float):
        dt = min(dt, DT_MAX)
        seg_before = self.current_segment
        if seg_before.type == "straight":
            self._step_straight(seg_before, dt)
        else:
            self._step_corner(seg_before, dt)
        # Периодические события каждые 7.5с на одном участке
        if (self.state.total_time - self._last_seg_evt_time) >= 7.5:
            self._notify({
                "type": "segment_tick",
                "segment": seg_before.name,
                "segment_id": self.state.current_segment_idx + 1,
                "segment_length": seg_before.length,
                "distance": self.state.segment_distance,
                "lap": self.state.current_lap,
                "laps": self.laps,
                "time_s": self.state.total_time,
                "speed": self.state.speed * 3.6,
            })
            self._last_seg_evt_time = self.state.total_time
        if self.state.segment_distance >= seg_before.length:
            excess = self.state.segment_distance - seg_before.length
            self.state.segment_distance = excess
            self.state.current_segment_idx += 1
            if self.state.current_segment_idx >= len(self.track.segments):
                self.state.current_segment_idx = 0
                self.state.current_lap += 1
                self._notify({
                    "type": "lap_complete",
                    "lap": self.state.current_lap - 1,
                    "time_s": self.state.total_time,
                })
                if self.state.current_lap > self.laps:
                    self.state.is_finished = True
                    self._notify({
                        "type": "race_complete",
                        "time_s": self.state.total_time,
                        "incidents": self.state.incidents,
                    })
            else:
                self._notify({
                    "type": "segment_change",
                    "segment": self.current_segment.name,
                    "segment_id": self.state.current_segment_idx + 1,
                    "lap": self.state.current_lap,
                    "laps": self.laps,
                    "time_s": self.state.total_time,
                    "speed": self.state.speed * 3.6,
                })
            # новая секция – сбрасываем таймер сегмента
            self._last_seg_evt_time = self.state.total_time

    def run(self, dt: float = 0.1):
        while not self.state.is_finished:
            self.step(dt)

    def race_summary(self) -> Dict:
        km = self.track.total_length * self.laps / 1000.0
        return {
            "total_time_s": self.state.total_time,
            "km": km,
            "incidents": self.state.incidents,
            "clean_corners": self.state.clean_corners,
            "penalties": self.state.penalties,
        }

def run_race(car: Car, track: Track, laps: int, driver: DriverProfile,
             dt: float = 0.1, seed: int = 42,
             on_event: Optional[Callable[[Dict], None]] = None) -> Tuple[Dict, Dict[str, float]]:
    eng = RaceEngine(car, track, laps, driver=driver, seed=seed, on_event=on_event)
    eng.run(dt=dt)
    summary = eng.race_summary()
    gains = driver.update_after_race(km_driven=summary["km"],
                                     incidents=summary["incidents"],
                                     clean_corners=summary["clean_corners"])
    if on_event:
        for k, dv in gains.items():
            if dv > 0.0:
                on_event({"type": "skill_up", "skill": k, "delta": dv, "new": getattr(driver, k)})
    return summary, gains
