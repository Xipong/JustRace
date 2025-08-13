import importlib, os, pathlib

def test_bonus_code_reward(tmp_path, monkeypatch):
    monkeypatch.setenv("GAME_DATA_DIR", str(tmp_path))
    import economy_v1
    importlib.reload(economy_v1)
    p = economy_v1.load_player("42", "Tester")
    msg = economy_v1.redeem_bonus_code(p, "TestNewBounty")
    assert "100000" in msg
    assert p.balance == economy_v1.DEFAULT_START_BALANCE + 100_000
    repo_data = pathlib.Path(__file__).resolve().parent.parent / "data"
    monkeypatch.setenv("GAME_DATA_DIR", str(repo_data))
    importlib.reload(economy_v1)
