import time
from pathlib import Path

from aegis import uploaders, update
from aegis.clips import Catalog, Clip


# ───────── uploader registry / selection ─────────
def test_build_enabled_returns_only_on_targets(cfg):
    cfg.set("uploads.discord.enabled", True)
    names = [u.name for u in uploaders.build_enabled(cfg)]
    assert "gallery" in names and "discord" in names
    assert "telegram" not in names


def test_gallery_uploader_ok_for_existing_file(cfg, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    res = uploaders.GalleryUploader(cfg).send(f, "cap")
    assert res.ok


def test_unconfigured_targets_report_not_configured(cfg, tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    assert not uploaders.TelegramUploader(cfg).send(f, "cap").ok
    assert not uploaders.DiscordUploader(cfg).send(f, "cap").ok
    assert not uploaders.YouTubeUploader(cfg).send(f, "cap").ok


# ───────── update semver ─────────
def test_semver_compare():
    assert update.is_newer("v2.1.0", "2.0.0")
    assert update.is_newer("2.0.1", "2.0.0")
    assert not update.is_newer("2.0.0", "2.0.0")
    assert not update.is_newer("v1.9.9", "2.0.0")
    assert update._parse("v2.10.1") == (2, 10, 1)


def test_update_check_noop_for_placeholder_repo(cfg):
    cfg.set("update.repo", "OWNER/REPO")
    assert update.check(cfg) is None      # never touches the network


# ───────── catalog ─────────
def test_catalog_add_update_remove_persist(data_dir):
    cat = Catalog()
    c = Clip(id="a1", path=str(data_dir / "a.mp4"), created=time.time(), kills=3)
    cat.add(c)
    assert cat.update("a1", title="My Ace", favorite=True).favorite
    # reload from disk -> persisted
    assert Catalog().get("a1").title == "My Ace"
    assert cat.remove("a1")
    assert Catalog().get("a1") is None


def test_catalog_list_newest_first(data_dir):
    cat = Catalog()
    cat.add(Clip(id="old", path="x", created=100.0))
    cat.add(Clip(id="new", path="x", created=200.0))
    assert [c.id for c in cat.list()] == ["new", "old"]
