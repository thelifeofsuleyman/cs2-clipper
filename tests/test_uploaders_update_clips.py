import time
from pathlib import Path
from types import SimpleNamespace

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


def test_discord_uploads_a_bounded_copy_from_a_separate_folder(cfg, tmp_path, monkeypatch):
    from aegis.uploaders import discord

    source = tmp_path / "source.mp4"
    source.write_bytes(b"recording")
    cfg.set("uploads.discord.webhook_url", "https://discord.com/api/webhooks/1/test-token")
    cfg.set("uploads.discord.max_mb", 0.000007)
    copies = []

    def encode(_ffmpeg, video, out, limit):
        assert video == source and limit == 7
        assert out.parent != source.parent
        out.write_bytes(b"copy")
        copies.append(out)
        return True

    def post(_url, *, files, **kwargs):
        assert files["file"][1].read() == b"copy"
        assert kwargs["allow_redirects"] is False
        return SimpleNamespace(status_code=204)

    monkeypatch.setattr(discord.media, "reencode_to_fit", encode)
    monkeypatch.setattr(discord.requests, "post", post)
    assert uploaders.DiscordUploader(cfg).send(source, "Clip").ok
    assert not copies[0].parent.exists()
    assert source.read_bytes() == b"recording"


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


def test_update_requires_exact_installer_and_digest(cfg, monkeypatch):
    version = "v99.0.0"
    url = f"{update._RELEASES}/download/{version}/{update._INSTALLER}"
    asset = {"name": update._INSTALLER, "browser_download_url": url, "size": 2}
    payload = {"tag_name": version, "assets": [asset]}
    monkeypatch.setattr(update.requests, "get", lambda *a, **kw: SimpleNamespace(
        status_code=200, json=lambda: payload))
    assert update.check(cfg).asset_url == ""
    asset["digest"] = "sha256:" + "a" * 64
    assert update.check(cfg).asset_url == url
    asset["name"] = "other.exe"
    assert update.check(cfg).asset_url == ""


def test_update_checks_are_reused_until_github_allows_retry(cfg, monkeypatch):
    clock = [1_000.0]
    calls = []
    limited = SimpleNamespace(status_code=429, headers={"X-RateLimit-Remaining": "0",
                                                       "X-RateLimit-Reset": "1065"})
    success = SimpleNamespace(status_code=200, json=lambda: {"tag_name": "v99.0.0", "assets": []})
    monkeypatch.setattr(update, "time", SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0]))

    def get(*args, **kwargs):
        calls.append(True)
        return limited if len(calls) == 1 else success

    monkeypatch.setattr(update.requests, "get", get)
    checker = update.ReleaseChecker(cfg)
    first = checker.check()
    assert first.error and first.retry_at == 1065
    clock[0] += 31
    assert checker.check(manual=True) == first
    assert len(calls) == 1
    clock[0] = 1065
    assert checker.check(manual=True).info.version == "99.0.0"
    clock[0] += 20
    assert checker.check().info.version == "99.0.0"
    assert checker.check(manual=True).info.version == "99.0.0"
    assert len(calls) == 2
    clock[0] += 10
    assert checker.check(manual=True).info.version == "99.0.0"
    assert len(calls) == 3


# ───────── catalog ─────────
def test_catalog_add_update_remove_persist(data_dir):
    cat = Catalog()
    c = Clip(id="a1", path=str(data_dir / "a.mp4"), created=time.time(), kills=3)
    cat.add(c)
    assert cat.update("a1", title="My Ace", favorite=True).favorite
    # reload from disk -> persisted
    assert Catalog().get("a1").title == "My Ace"
    cat.update("a1", favorite=False)
    assert cat.remove("a1")
    assert Catalog().get("a1") is None


def test_catalog_list_newest_first(data_dir):
    cat = Catalog()
    cat.add(Clip(id="old", path="x", created=100.0))
    cat.add(Clip(id="new", path="x", created=200.0))
    assert [c.id for c in cat.list()] == ["new", "old"]
