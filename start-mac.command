#!/bin/bash
# Double-click this in Finder to start the photobooth on a Mac.
# The first run sets things up inside this folder (needs internet, takes a minute or two).
# Nothing gets installed outside this folder.

cd "$(dirname "$0")" || exit 1

finish() {
  echo
  read -r -p "Press Return to close this window. " _
  exit "$1"
}

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import sys" >/dev/null 2>&1; then
  echo "Python 3 isn't ready on this Mac."
  echo "If a window popped up asking to install developer tools, click Install, wait for it"
  echo "to finish, then double-click this file again."
  echo "Or install Python from https://www.python.org/downloads/ and try again."
  finish 1
fi
if ! python3 -c "import sys; sys.exit(sys.version_info < (3, 9))"; then
  echo "This needs Python 3.9 or newer. This Mac has $(python3 --version 2>&1)."
  echo "Install a newer one from https://www.python.org/downloads/ and try again."
  finish 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First run: setting things up. This takes a minute or two and needs internet."
  python3 -m venv .venv || { echo "Couldn't create the .venv folder."; finish 1; }
fi
# Checking the imports (not just whether .venv exists) means a setup that got cut off
# halfway, e.g. by a dropped connection, fixes itself on the next double-click.
if ! .venv/bin/python -c "import cv2, PIL, numpy" >/dev/null 2>&1; then
  echo "Installing the libraries the booth needs..."
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt || {
    echo
    echo "Setup didn't finish. Check the internet connection and double-click this again."
    finish 1
  }
fi

.venv/bin/python booth.py "$@"
finish $?
