"""Shared fixtures. Every test gets an isolated %APPDATA% so config/catalog
writes never touch the real user data dir."""
import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point Aegis's data root at a temp dir for the duration of a test."""
    monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def cfg(data_dir):
    from aegis import config
    return config.load()


@pytest.fixture
def app_client(cfg):
    """Flask test client wired to a fresh engine + catalog."""
    from aegis import web
    from aegis.clips import Catalog
    from aegis.engine import Engine
    catalog = Catalog()
    engine = Engine(cfg, catalog)
    application = web.create_app(cfg, catalog, engine)
    application.testing = True
    return application.test_client(), cfg, catalog, engine
