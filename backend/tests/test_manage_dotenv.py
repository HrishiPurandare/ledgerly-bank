import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("manage", Path(__file__).resolve().parents[1] / "manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def test_dotenv_values_are_loaded_but_real_environment_wins(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nLB_A=from-file\nLB_B='quoted'\nLB_C=from-file\n\nnot a pair\n")
    monkeypatch.delenv("LB_A", raising=False)
    monkeypatch.delenv("LB_B", raising=False)
    monkeypatch.setenv("LB_C", "from-shell")
    manage.load_dotenv(env)
    import os

    assert os.environ["LB_A"] == "from-file"
    assert os.environ["LB_B"] == "quoted"
    assert os.environ["LB_C"] == "from-shell"
    for key in ("LB_A", "LB_B"):
        monkeypatch.delenv(key)


def test_a_missing_dotenv_is_fine(tmp_path):
    manage.load_dotenv(tmp_path / "nope.env")
