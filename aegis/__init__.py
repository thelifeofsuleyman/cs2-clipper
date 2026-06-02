"""Aegis Clipper — local-first automatic CS2 highlight clipper.

A polished evolution of the original single-file clipper. Detects kill
streaks via CS2 Game State Integration, tells OBS to save its replay buffer,
then catalogs the clip locally and fans it out to any enabled upload target
(Telegram, Discord, YouTube, local gallery). Ships with a web dashboard,
auto-montage builder, and a guided setup wizard.

Package layout:
  paths       - per-user data/config directories
  log         - tiny timestamped logger with an in-memory ring buffer
  config      - JSON settings store (+ migration from legacy .env)
  obs_client  - OBS WebSocket wrapper (lazy, failure tolerant)
  engine      - GSI listener + debounce + clip pipeline (the original core)
  media       - ffmpeg helpers (thumbnails, montage, re-encode to fit)
  clips       - clip catalog (metadata persisted to JSON)
  uploaders/  - pluggable upload targets
  dashboard/  - local web UI + setup wizard
  app         - process entry: engine + dashboard + system tray
"""

__version__ = "2.1.2"
APP_NAME = "Aegis Clipper"
