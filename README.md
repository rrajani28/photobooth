# Photobooth

The booth shows a live webcam preview. When someone presses SPACE (or a physical button on the Pi), it runs a 3-2-1 countdown, takes 4 photos, builds a photobooth strip, and sends it to a printer.

The same code runs on a laptop (Mac or Windows) and on a Raspberry Pi. Everything you change lives in `config.json`.

```
booth.py         main app: preview, countdown, flash, review screen
camera.py        webcam access (plus a fake camera for testing)
strip.py         builds the 2x6 strip, or a 4x6 sheet with two strips to cut apart
printer.py       printing: none / system printer / USB thermal printer
trigger.py       SPACE key or GPIO push button
config.json      all settings
tests/           run with: python -m pytest -q   (needs: pip install -r requirements-dev.txt)
```

## 1. Run it on your laptop

```bash
cd photobooth
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # or requirements-dev.txt to also get pytest

python booth.py --list-cameras     # saves a snapshot from each camera in output/cameras/
python booth.py                    # run it (uses camera.index from config.json)
python booth.py --camera 0         # ...or pick a camera just for this run
```

**Which camera is which:** don't guess from the number. `--list-cameras` saves `output/cameras/camera_0.jpg`, `camera_1.jpg`, … so you can look, and it flags any camera that only sends black.

**Camera index on this MacBook:** `camera.index` is `1`, because Rohan's iPhone shows up as camera `0` (Continuity Camera). If the iPhone isn't nearby, or Continuity Camera is switched off on it, the MacBook camera moves to `0`. **The USB webcam on the Pi will have its own index too.** Run `--list-cameras` on the Pi and set `camera.index` to whatever it shows.

Controls: **SPACE** starts a session, **F** toggles fullscreen, and **Q** or **ESC** quits.

You can test without a webcam by running `python booth.py --fake-camera`.

Every session is saved in `output/<date_time>/` with these files:

- `shot_1.jpg` … `shot_4.jpg`: the full-resolution photos
- `strip.png`: one 2x6 strip
- `print.png`: the file that actually gets printed (set by `layout`)

**Mac:** the first time you run it, macOS asks for camera permission for Terminal (or VS Code). If the window stays black, go to System Settings → Privacy & Security → Camera and allow it.

macOS gives camera permission to the *app* you launch the booth from, not to Python. Run it from **Terminal.app**. Terminals built into other apps (the Claude desktop app's terminal, for example) can be blocked from the camera with no popup at all. If you see `not authorized to capture video` and no permission popup appears, that's why.

## 2. Settings worth changing (`config.json`)

| Setting | What it does |
|---|---|
| `camera.index` | Which camera to use (see `--list-cameras`) |
| `shots` | Photos per strip. 3 or 4 looks right |
| `countdown_seconds` | Length of the countdown before each photo |
| `strip.footer_text` | Text at the bottom of the strip, such as an event name |
| `strip.layout` | `4x6_double` = two strips on one 4x6 sheet (for photo printers, cut down the middle). `strip` = a single strip (for thermal printers) |
| `strip.grayscale` | Black and white strips |
| `mirror_preview` | Mirrors the screen like a selfie camera. The saved photos aren't mirrored, so any text in the background reads correctly |
| `printer.backend` | `preview`, `none`, `system`, or `escpos` (see below) |
| `trigger.gpio_pin` | Set to `17` on the Pi to use a physical button |

## 3. Printing

**Color or black and white?** `preview` and `system` print in full color. `escpos` (thermal) is always black and white, because thermal paper can only make black dots. For a black and white strip on *any* printer, set `strip.grayscale` to `true`.

**`preview`** (default, no printer needed): saves `print.pdf` at its true physical size (4x6 in) and pops it open on screen when the session ends, like a print sliding out. On a Mac it opens *behind* the booth window, so the booth keeps the keyboard and the next SPACE still works. Switch to Preview to look at it. If you want real prints later, take `print.png` to any drugstore photo kiosk as a standard 4x6 print and cut it down the middle. To see the true size before printing, open the PDF and print it at 100% (not "fit to page") on any printer.

**`none`**: saves the files only, with no pop-up.

**`system`**: for a normal photo printer such as a Canon Selphy.

- **Mac/Pi:** the photo goes through CUPS (`lp`). Run `lpstat -p` to see printer names, then put one in `printer_name`.
- **Windows:** it uses the default printer.
- On the Pi, run `sudo apt install cups printer-driver-gutenprint` first, then add the printer at `http://localhost:631`. Check that your exact printer model is supported before you buy one.

**`escpos`**: for a USB thermal receipt printer (58mm). This path needs no drivers and is the cheapest to run. Prints come out black and white with a "receipt" look.

```bash
pip install python-escpos
lsusb                       # on the Pi, e.g. "ID 0416:5011" -> vendor 0x0416, product 0x5011
```

Put those IDs in `escpos_vendor_id` and `escpos_product_id`, and set `layout` to `strip`. For an 80mm printer, also set `thermal_width_px` to 576.

## 4. Move it to the Raspberry Pi

This needs a Pi 4 or Pi 5 running Raspberry Pi OS with desktop. A Pi Zero is too slow for a smooth live preview.

```bash
sudo apt update
sudo apt install -y python3-opencv python3-pil python3-numpy cups
# copy the photobooth folder over (USB stick, scp, or git), then:
cd photobooth
python3 booth.py --list-cameras
python3 booth.py --headless          # one test session, no window; works over SSH
python3 booth.py                     # the real thing, on the Pi's screen
```

For the thermal printer on the Pi:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install python-escpos
# let your user talk to the printer without sudo (swap in your IDs from lsusb):
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0416", ATTRS{idProduct}=="5011", MODE="0666"' | sudo tee /etc/udev/rules.d/99-thermal.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
.venv/bin/python booth.py
```

### Physical button

Wire any momentary push button like this:

| Button leg | Pi pin |
|---|---|
| One leg | GPIO17 (physical pin 11) |
| Other leg | GND (physical pin 9) |

You don't need a resistor. Then set `"trigger": { "gpio_pin": 17 }` and `"fullscreen": true`.

### Start automatically on boot (optional)

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/photobooth.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Photobooth
Exec=python3 /home/$USER/photobooth/booth.py
EOF
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Black window or "couldn't open camera" | Try another index from `--list-cameras`. On a Mac, check the camera permission. Close Zoom, FaceTime, and anything else using the camera |
| `WARNING: camera N is sending an all-black image` | Probably the wrong camera. On a Mac, a nearby iPhone (Continuity Camera) can take an index. Check the snapshots from `--list-cameras` |
| `not authorized to capture video`, and no popup ever appears | You're running it from a terminal inside another app. Use Terminal.app, then allow it under Privacy & Security → Camera |
| Fonts on the strip aren't bold | No bold system font was found. On the Pi: `sudo apt install fonts-dejavu-core` |
| Laggy preview | Lower the camera to `1280x720` in config |
| Dark or orange photos | That's lighting, not code. A cheap ring light or lamp aimed at faces fixes it more than any camera upgrade |
| Faces cut off at the edges | Each slot crops the middle of the frame. Have people stand closer to the center |
| Thermal print looks washed out | It's already auto-contrasted. Better light at capture time is the real fix |
