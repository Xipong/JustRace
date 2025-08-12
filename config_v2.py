# Централизованные параметры физики/прогрессии
USE_ROLLING_RESISTANCE = True
C_RR = 0.012
K_LAT = 0.90
ERROR_RATE_BASE = 0.002
TIME_PENALTY_RANGE = (0.10, 0.35)
DT_MAX = 0.1

XP_PER_KM = 1.0
PROGRESSION = {
    "braking":     {"eta": 0.60, "target": 92.0},
    "consistency": {"eta": 0.40, "target": 88.0},
    "stress":      {"eta": 0.50, "target": 94.0},
}
