import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models_v2 import Car, Track, TrackSegment, RaceEngine


def test_race_events_include_speed():
    car = Car(id="c", name="Car", power=100, mass=1000, cd=0.35, area=2.0, tire_grip=1.0)
    track = Track(
        "t",
        "Test",
        [
            TrackSegment("s1", "straight", 100, 1, 1, 1, 1),
            TrackSegment("s2", "straight", 100, 1, 1, 1, 1),
        ],
    )
    speeds = []

    def on_evt(evt):
        if evt["type"] in ("segment_tick", "segment_change"):
            speeds.append(evt["speed"])

    eng = RaceEngine(car, track, laps=1, on_event=on_evt)
    eng.run(dt=0.1)
    assert speeds and all(isinstance(s, float) for s in speeds)
