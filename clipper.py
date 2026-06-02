"""Backward-compatible launcher.

The original single-file clipper has grown into the ``aegis`` package (engine +
web dashboard + uploaders + montage + setup wizard). This shim keeps the old
muscle memory working: ``python clipper.py`` now boots the full app, and
``python clipper.py --headless`` runs the engine + dashboard with no tray icon,
matching the original console-only behaviour.

See README.md / CLAUDE.md for the new architecture, or just run it and the setup
wizard opens in your browser.
"""
import sys

from aegis.app import main

if __name__ == "__main__":
    sys.exit(main())
