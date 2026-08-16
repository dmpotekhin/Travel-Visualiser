import pytest

from backend import config, database


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point the app at an isolated SQLite file for each test."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    return config.DB_PATH
