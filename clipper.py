"""CS2 auto-clipper — debounced multi-kill bundling.

Listens to CS2's Game State Integration (GSI) on a local port. When your
kill count goes up, starts a 7-second debounce timer. Each additional kill
resets it. When the timer expires (no kill for 7 sec), the bot tells OBS to
save the replay buffer, then uploads the resulting clip to a Telegram
channel with an auto-generated caption.

Result:
  - Solo kill         -> one ~30 sec clip
  - Double / triple   -> one clip covering both kills
  - Ace               -> one clip covering all 5 kills

Architecture:
  CS2 GSI  ->  Flask :3000  ->  debounce timer  ->  OBS WebSocket
                                                    ->  watch output dir
                                                    ->  Telegram sendVideo

Config: see .env.example for environment variables.
"""
from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request
from obsws_python import ReqClient
from obsws_python.error import OBSSDKError

load_dotenv()

# ───────── config ─────────
DEBOUNCE_SEC   = float(os.getenv("DEBOUNCE_SEC", "7"))
TG_BOT_TOKEN   = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID     = os.getenv("TG_CHAT_ID", "")
OBS_HOST       = os.getenv("OBS_HOST", "localhost")
OBS_PORT       = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD   = os.getenv("OBS_PASSWORD", "")
OBS_REPLAY_DIR = Path(os.getenv("OBS_REPLAY_DIR", str(Path.home() / "Videos")))
GSI_PORT       = int(os.getenv("GSI_PORT", "3000"))
CLIP_WAIT_SEC  = float(os.getenv("CLIP_WAIT_SEC", "8"))
MIN_KILLS      = int(os.getenv("MIN_KILLS", "1"))  # set to 2 to skip solo kills


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ───────── state (thread-protected) ─────────
state = {
    "last_match_kills": -1,   # -1 = uninitialised (first tick will sync, not fire)
    "pending_kills":    0,
    "first_kill_ts":    0.0,
    "last_kill_ts":     0.0,
    "map_name":         "unknown",
    "round_n":          0,
    "side":             "?",
    "debounce_timer":   None,
}
state_lock = threading.Lock()


# ───────── OBS connection ─────────
_obs: ReqClient | None = None


def obs() -> ReqClient | None:
    """Lazy OBS WebSocket client. Returns None if OBS isn't reachable."""
    global _obs
    if _obs is None:
        try:
            _obs = ReqClient(
                host=OBS_HOST,
                port=OBS_PORT,
                password=OBS_PASSWORD or None,
                timeout=3,
            )
            log(f"OBS WebSocket connected at {OBS_HOST}:{OBS_PORT}")
        except Exception as e:
            log(f"OBS WebSocket unreachable: {e}")
            _obs = None
    return _obs


# ───────── Flask listener ─────────
app = Flask(__name__)


@app.route("/", methods=["POST"])
def gsi_in():
    try:
        payload = request.get_json(silent=True) or {}
        handle_payload(payload)
    except Exception as e:
        log(f"handle_payload error: {e}")
    return "", 200


@app.route("/health", methods=["GET"])
def health():
    return {
        "ok": True,
        "obs_connected": obs() is not None,
        "debounce_sec": DEBOUNCE_SEC,
        "telegram_configured": bool(TG_BOT_TOKEN and TG_CHAT_ID),
    }, 200


def handle_payload(p: dict) -> None:
    """Parse one GSI tick and update kill state."""
    player = p.get("player") or {}
    match_stats = player.get("match_stats") or {}
    map_obj = p.get("map") or {}

    current_kills = int(match_stats.get("kills", 0))
    map_name = map_obj.get("name", "unknown")
    round_n = int(map_obj.get("round", 0))
    team = (player.get("team") or "?").upper()

    with state_lock:
        prev = state["last_match_kills"]

        # First tick or new match (kill counter reset)
        if prev == -1 or current_kills < prev:
            if prev != -1:
                log(f"New match / reset detected (kills {prev} -> {current_kills})")
            state["last_match_kills"] = current_kills
            state["pending_kills"] = 0
            state["first_kill_ts"] = 0.0
            return

        diff = current_kills - prev
        state["last_match_kills"] = current_kills

        if diff <= 0:
            return  # no new kills

        # New kill(s) since last tick
        now = time.time()
        state["pending_kills"] += diff
        state["last_kill_ts"] = now
        if state["first_kill_ts"] == 0:
            state["first_kill_ts"] = now
        state["map_name"] = map_name
        state["round_n"] = round_n
        state["side"] = team

        log(f"Kill +{diff} (total pending: {state['pending_kills']}) on {map_name} round {round_n}")
        schedule_save()


def schedule_save() -> None:
    """Cancel any pending save timer and start a new one."""
    if state["debounce_timer"] is not None:
        state["debounce_timer"].cancel()
    t = threading.Timer(DEBOUNCE_SEC, save_clip)
    t.daemon = True
    state["debounce_timer"] = t
    t.start()


# ───────── clip pipeline ─────────
def save_clip() -> None:
    """Trigger OBS replay save, wait for the file, upload to Telegram."""
    with state_lock:
        kills = state["pending_kills"]
        map_name = state["map_name"]
        round_n = state["round_n"]
        side = state["side"]
        state["pending_kills"] = 0
        state["first_kill_ts"] = 0.0

    if kills < MIN_KILLS:
        return

    log(f"Triggering save_replay_buffer for {kills} kill(s)")

    client = obs()
    if client is None:
        log("OBS not reachable — clip not saved")
        return

    try:
        client.save_replay_buffer()
    except OBSSDKError as e:
        log(f"OBS save_replay_buffer rejected: {e}")
        return
    except Exception as e:
        log(f"OBS save_replay_buffer error: {e}")
        return

    clip = wait_for_new_clip(CLIP_WAIT_SEC)
    if clip is None:
        log(f"No new clip appeared in {OBS_REPLAY_DIR} within {CLIP_WAIT_SEC}s — check Replay Buffer enabled in OBS")
        return

    caption = format_caption(kills, map_name, round_n, side)
    upload_to_telegram(clip, caption)


def wait_for_new_clip(timeout: float) -> Path | None:
    """Poll the OBS output dir for a video file newer than `start`."""
    start = time.time()
    deadline = start + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            candidates = [
                f for f in OBS_REPLAY_DIR.iterdir()
                if f.is_file()
                and f.suffix.lower() in (".mp4", ".mkv", ".mov")
                and f.stat().st_mtime >= start - 1
            ]
        except FileNotFoundError:
            log(f"OBS replay dir not found: {OBS_REPLAY_DIR}")
            return None
        if candidates:
            latest = max(candidates, key=lambda f: f.stat().st_mtime)
            # Wait a moment for OBS to finish writing
            prev_size = -1
            for _ in range(10):
                size = latest.stat().st_size
                if size > 0 and size == prev_size:
                    return latest
                prev_size = size
                time.sleep(0.3)
            return latest
    return None


KILL_LABELS = {
    1: ("Kill", ""),
    2: ("Double tap", ""),
    3: ("TRIPLE", ""),
    4: ("QUAD", ""),
    5: ("ACE", ""),
}


def format_caption(kills: int, map_name: str, round_n: int, side: str) -> str:
    label, _ = KILL_LABELS.get(kills, (f"{kills}K", ""))
    parts = [label, f"on {map_name}"]
    if round_n > 0:
        parts.append(f"(round {round_n}, {side}-side)")
    return " ".join(parts)


def upload_to_telegram(clip_path: Path, caption: str) -> None:
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        log(f"Clip ready ({clip_path.name}) but Telegram not configured")
        return

    size_mb = clip_path.stat().st_size / (1024 * 1024)
    log(f"Uploading {clip_path.name} ({size_mb:.1f} MB) -> Telegram: '{caption}'")

    try:
        with clip_path.open("rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendVideo",
                data={
                    "chat_id": TG_CHAT_ID,
                    "caption": caption,
                    "supports_streaming": True,
                },
                files={"video": (clip_path.name, f, "video/mp4")},
                timeout=300,
            )
    except Exception as e:
        log(f"Telegram upload exception: {e}")
        return

    if r.ok:
        log(f"Uploaded OK")
    else:
        log(f"Telegram error {r.status_code}: {r.text[:200]}")


# ───────── main ─────────
def banner() -> None:
    log("=" * 64)
    log("CS2 auto-clipper — debounce bundle mode")
    log(f"  GSI listener:    http://127.0.0.1:{GSI_PORT}")
    log(f"  debounce:        {DEBOUNCE_SEC} sec")
    log(f"  min kills/clip:  {MIN_KILLS}")
    log(f"  OBS WebSocket:   {OBS_HOST}:{OBS_PORT}")
    log(f"  OBS replay dir:  {OBS_REPLAY_DIR}")
    log(f"  Telegram bot:    {'configured' if TG_BOT_TOKEN else 'NOT SET'}")
    log(f"  Telegram chat:   {TG_CHAT_ID or 'NOT SET'}")
    log("=" * 64)


def main() -> None:
    banner()
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        log("WARNING: Telegram is not configured. Clips will be saved by OBS but not uploaded.")
        log("Edit .env to set TG_BOT_TOKEN and TG_CHAT_ID")
    # Pre-warm OBS connection so the first kill doesn't pay the connect cost
    obs()
    # Flask dev server is fine here — GSI traffic is local, very low volume
    app.run(host="127.0.0.1", port=GSI_PORT, threaded=True, debug=False)


if __name__ == "__main__":
    sys.exit(main() or 0)
