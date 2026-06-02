import json

from aegis import config
from aegis.paths import config_file


def test_defaults_present(cfg):
    assert cfg.get("recording.backend") == "builtin"
    assert cfg.get("engine.debounce_sec") == 7.0
    assert cfg.get("uploads.gallery.enabled") is True


def test_dotted_get_set(cfg):
    cfg.set("recording.preset", "low")
    assert cfg.get("recording.preset") == "low"
    assert cfg.get("nope.missing", "fallback") == "fallback"


def test_update_deep_merges(cfg):
    cfg.update({"uploads": {"discord": {"enabled": True, "webhook_url": "x"}}})
    assert cfg.get("uploads.discord.enabled") is True
    # sibling keys untouched
    assert cfg.get("uploads.telegram.enabled") is False
    assert cfg.get("uploads.gallery.enabled") is True


def test_save_and_reload_roundtrip(cfg, data_dir):
    cfg.set("recording.clip_seconds", 42)
    cfg.save()
    reloaded = config.load()
    assert reloaded.get("recording.clip_seconds") == 42


def test_load_merges_new_defaults_into_old_file(data_dir):
    # simulate an old config file missing the newer "recording" section
    old = {"first_run": False, "engine": {"debounce_sec": 5}}
    config_file().write_text(json.dumps(old), encoding="utf-8")
    cfg = config.load()
    assert cfg.get("engine.debounce_sec") == 5          # preserved
    assert cfg.get("recording.backend") == "builtin"    # merged from defaults
    assert cfg.get("first_run") is False


def test_env_migration(tmp_path, monkeypatch):
    # a legacy .env at the repo root is imported on first load
    import aegis.config as c
    repo_env = c.Path(c.__file__).resolve().parent.parent / ".env"
    created = False
    if not repo_env.exists():
        repo_env.write_text("TG_BOT_TOKEN=abc\nTG_CHAT_ID=-100\nDEBOUNCE_SEC=9\n", encoding="utf-8")
        created = True
    try:
        monkeypatch.setenv("AEGIS_DATA_DIR", str(tmp_path))
        cfg = config.load()
        # Only assert when we own the file we created (don't trample a real .env).
        if created:
            assert cfg.get("engine.debounce_sec") == 9
            assert cfg.get("uploads.telegram.enabled") is True
    finally:
        if created:
            repo_env.unlink()
