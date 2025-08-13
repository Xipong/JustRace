import importlib
import os

def test_premium_unlimited_races(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_DATA_DIR", str(tmp_path))
    from pathlib import Path
    (Path(tmp_path) / "premium.txt").write_text("42\n", encoding="utf-8")
    import premium
    importlib.reload(premium)
    import economy_v1
    importlib.reload(economy_v1)
    import game_api
    importlib.reload(game_api)
    p = economy_v1.load_player("42", "Tester")
    for _ in range(game_api.MAX_RACES_PER_DAY + 5):
        game_api._check_daily_limit(p)
