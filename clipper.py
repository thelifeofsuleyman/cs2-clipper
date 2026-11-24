"""Launch Aegis from PyInstaller or existing source scripts."""
import sys

from aegis.app import main

if __name__ == "__main__":
    sys.exit(main())
