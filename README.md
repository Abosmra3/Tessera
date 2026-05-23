<div align="center">

<img src="icon.ico" width="96" height="96" alt="Tessera"/>

# Tessera

**A Windows desktop utility for screen-based pattern recognition helpers and configurable hotkey workflows.**

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow.svg)](#)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)

</div>

---

## Table of Contents

* [Setup](#setup)
* [Compile the code yourself](#compile-the-code-yourself)
* [Tested resolutions (16:9)](#tested-resolutions-169)
* [How to use the tool](#how-to-use-the-tool)
  * [How to use the fingerprint helpers](#how-to-use-the-fingerprint-helpers)
  * [How to use Nosave](#how-to-use-nosave)
  * [How to use Job Warp](#how-to-use-job-warp)
* [License](#license)
* [Disclaimer](#disclaimer)


## Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Compile the code yourself

```bash
pyinstaller main.py `
  --onefile `
  --uac-admin `
  --icon=icon.ico `
  --name "tessera" `
  --add-data "assets;assets"
```

## Tested resolutions (16:9)

- Supported aspect ratio: **16:9 only**. The tool was validated on the following resolutions:
  - 1600×900
  - 1920×1080 (Full HD)
  - 2560×1440 (QHD)

- Recommended setup:
  - Run the target application in **fullscreen**, **borderless fullscreen**, or **windowed** (borderless window preferred).
  - Set Windows display scaling to **100%** (DPI scaling can shift coordinates and break helpers).
  - Keep the tool's terminal window off the target display (use a second monitor, or minimize it).

- If your display is not 16:9 the helpers may be inaccurate. To troubleshoot:
  - Confirm the in-app resolution matches one of the tested values.
  - Confirm Windows scaling is 100% and that the target window is not overlapped by other windows.
  - If problems persist, try running the tool on a 16:9 display or report the issue with your resolution and scaling details.

## How to use the tool

### How to use the fingerprint helpers

Both helpers need to be positioned at the starting point of the puzzle. In short: when you begin, don't move the selector — then press the helper hotkey for each fingerprint.

- Make sure the tool is launched before you begin.

- Position the selector/cursor at the exact starting point of the puzzle and leave it there — do not move the selector during the puzzle.

- Begin and, when required, press the appropriate helper hotkey:
  - **F6**: Casino helper
  - **F7**: Cayo helper

- Press the helper hotkey for each fingerprint as it appears. The helper reads from the fixed selector position, so moving it will cause incorrect results.

- Test the helper once on your setup before relying on it. If it works once it should keep working unless you change system configuration or aspect ratio.


### How to use Nosave

- Make sure the tool is launched beforehand to be safe.

- When you toggle Nosave with `F8` you should see a small HUD banner in the top-right of your screen indicating the state: `No Save ON` (green) when enabled and `No Save OFF` (red) when disabled. If you don't see the banner, ensure the tool's dependencies are installed and that overlays are not blocked by other software.

- Toggle Nosave **on** shortly before the moment you want to prevent a save (10–20 seconds is a safe buffer).

- Continue normally and wait until you are back in control before disabling.

- Once you are fully loaded back (no loading indicators), disable Nosave with `F8`.

- After disabling, you can resume normal play.

- While Nosave-affecting actions are pending, avoid any prompts or external menus that may force a save.

### How to use Job Warp

- Make sure the tool is running.
- Set Matchmaking to **Closed** in the relevant menu.
- On the map, hover over the destination you want to warp to.
- Press **F5** while the destination is highlighted (ensure the start action is visible at the bottom of the screen) to warp to it.


## License

This project is licensed under the **GNU General Public License v2.0** — see the [LICENSE](LICENSE) file for full terms.

## Disclaimer

For educational purposes only. The author/s are not responsible for any consequences including but not limited to account actions, data loss, or violations of terms of service.
