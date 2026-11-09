@echo off
rem Double-click this to start the photobooth on Windows.
rem The first run sets things up inside this folder (needs internet, takes a minute or two).
rem Nothing gets installed outside this folder.
setlocal
cd /d "%~dp0"

rem "py" is the launcher python.org installs. "python" alone can be a Microsoft Store
rem shortcut that isn't really Python, so actually run each one to check.
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
  goto havepython
)
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (
  set "PY=python"
  goto havepython
)
echo Python 3.9 or newer isn't installed (or isn't on the PATH).
echo Install it from https://www.python.org/downloads/
echo During setup, tick "Add python.exe to PATH". Then double-click this file again.
goto stop

:havepython
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting things up. This takes a minute or two and needs internet.
  %PY% -m venv .venv
  if errorlevel 1 goto setupfailed
)
rem Checking the imports means a setup that got cut off halfway fixes itself next time.
".venv\Scripts\python.exe" -c "import cv2, PIL, numpy" >nul 2>&1
if errorlevel 1 (
  echo Installing the libraries the booth needs...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto setupfailed
)

".venv\Scripts\python.exe" booth.py %*
goto stop

:setupfailed
echo.
echo Setup didn't finish. Check the internet connection and double-click this again.

:stop
echo.
pause
