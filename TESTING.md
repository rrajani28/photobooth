# Testing the photobooth

Thanks for helping me test this!

It's a photobooth. It shows a live camera preview. When you press SPACE, it counts down 3-2-1, takes 4 photos, and makes a 4x6 print with two photo strips on it. The final version will run on a Raspberry Pi with a webcam, a big button and a printer. For now it runs on a normal laptop with no printer: the "print" pops up as a PDF.

It takes about 15 minutes. Nothing is installed outside this folder and nothing is uploaded anywhere. Your photos stay in this folder. To remove everything afterwards, delete the folder.

## 1. What you need

- A Mac or Windows laptop with a webcam (built-in or USB).
- Internet the first time you start it. It downloads its libraries (about 170 MB) into this folder.
- Python 3.9 or newer:
  - **Mac:** you probably have it already. If not, the first start pops up an offer to install Apple's developer tools. Click **Install**, wait, then start again.
  - **Windows:** install it from [python.org/downloads](https://www.python.org/downloads/). During setup, tick **"Add python.exe to PATH"**.

## 2. Start it

Unzip the folder, then double-click:

- **Mac:** `start-mac.command`
- **Windows:** `start-windows.bat`

A text window opens. The first time, it spends a minute or two setting up. Then the booth window appears. If you don't see it, look behind the text window.

**If your computer refuses to open the file.** This is normal for scripts that come in an email or download, because they aren't signed by Apple or Microsoft.

- **Mac** ("Apple could not verify…"): click **Done**. Go to **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to `start-mac.command`. Or open **Terminal**, type `bash ` (with a space after it), drag `start-mac.command` into the Terminal window, and press Return.
- **Windows** ("Windows protected your PC"): click **More info → Run anyway**.

**Camera permission.**

- **Mac:** a popup asks if Terminal can use the camera. Click **Allow**. The first time, the booth may still say it couldn't open the camera, because macOS only gives access after that run. Close the window and double-click `start-mac.command` again. It only happens once. If you clicked Don't Allow by mistake, go to **System Settings → Privacy & Security → Camera** and switch on **Terminal**.
- **Windows:** if the picture stays black, go to **Settings → Privacy & security → Camera** and make sure **"Let desktop apps access your camera"** is on.

You might see `camera 1 can't be opened` followed by `Using camera 0 instead of 1`. That's normal: the settings are set up for my laptop, and the booth finds yours by itself.

## 3. How to use it

| Key | What it does |
|---|---|
| **SPACE** | Take a set of 4 photos |
| **F** | Fullscreen on/off |
| **Q** or **ESC** | Quit (closing the window works too) |

After the 4th photo, the print opens as a PDF:

- **Mac:** it opens *behind* the booth, so you can keep going. Click Preview in the Dock to look at it.
- **Windows:** it opens in front. Click back on the booth window before you press SPACE again.

Every round is saved in the `output` folder, one folder per round: the 4 photos, the strip, and the print.

## 4. What to try

1. Does the live picture show up within about 10 seconds, and does it move smoothly?
2. Hold up a book or a shirt with writing on it. The writing should read normally, both on screen and in the photos.
3. Press SPACE. Is the countdown easy to see? Are there 4 photos, with a short pause between them?
4. Open the print. Are any faces cut off? Is it too dark or too bright? Can you read the text at the bottom? Is the date right?
5. Press SPACE again and make sure a second round works too.
6. Try F for fullscreen. Then quit with Q, then with ESC, then with the window's close button.
7. Try harder shots: 3 or 4 people squeezed in, someone standing far back, a dim room, someone much taller than everyone else.
8. *Optional:* print `print.pdf` (it's inside each round's folder) at **100% / Actual size**, not "Fit to page". The sheet should measure exactly 4 x 6 inches.

**Optional, if you're comfortable with a terminal:** there are 56 automated tests. Open a terminal in this folder. On a Mac, type `cd `, drag the folder in, and press Return. On Windows, type `cmd` in the folder's address bar and press Enter. Then run:

Mac:

```bash
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

Windows:

```bat
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest -q
```

It should end with `56 passed`.

## 5. If something's wrong

| Problem | Fix |
|---|---|
| It's using the wrong camera (your phone, or a gray infrared one) | Open `config.json` in a text editor. Change `"index": 1` to `0` (or `2`), save, and start again |
| The booth window is black | Close anything else that uses the camera (Zoom, FaceTime, Teams, a browser tab), then start again |
| Keys don't do anything | Click on the booth window first, so it's the one listening to the keyboard |
| Anything else | The text window usually says what went wrong. There's also a Troubleshooting section at the end of `README.md` |

## 6. What to send me

- Your computer: Mac or Windows, and which version
- What worked, what didn't, and anything that was confusing
- If something broke: a screenshot of the text window (the error is usually in there)
- One or two strips from the `output` folder, if you're OK sharing them
- Any ideas to make it better

Thank you!
