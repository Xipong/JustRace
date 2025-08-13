import os
from pathlib import Path

DATA_DIR = Path(os.getenv("GAME_DATA_DIR", "./data"))
PREMIUM_FILE = DATA_DIR / "premium.txt"

def is_premium(user_id: str) -> bool:
    try:
        content = PREMIUM_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    ids = {line.strip() for line in content.splitlines() if line.strip()}
    return str(user_id) in ids
