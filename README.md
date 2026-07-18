<div align="center">

<img src="icon.ico" width="96" height="96" alt="Tessera"/>

# Tessera

**A Windows desktop utility for screen-based pattern recognition helpers and configurable hotkey workflows.**

[![License: GPL v2](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)](#)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow.svg)](#)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)
[![Downloads](https://img.shields.io/github/downloads/Abosmra3/Tessera/total?label=Downloads)](https://github.com/Abosmra3/Tessera/releases)
</div>

---

## Table of Contents

* [Setup](#setup)
* [Compile the code yourself](#compile-the-code-yourself)
* [Tested resolutions (16:9)](#tested-resolutions-169)
* [How to use the tool](#how-to-use-the-tool)
  * [How to use the fingerprint helpers](#how-to-use-the-fingerprint-helpers)
  * [How to use the keypad solver](#how-to-use-the-keypad-solver)
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

### Terminal UI status meanings

The live dashboard in the terminal shows a **Live Status** panel with these labels:

- **Game**
  - `UNDETECTED`: Tessera could not find the target game window.
  - `UNFOCUSED`: The target window was found, but it is not currently in the foreground.
  - `FOCUSED`: The target window is active and in focus.

- **Job Warp**
  - `READY`: The job warp helper is idle and waiting for input.
  - `RUNNING`: A job warp action is currently being executed.

- **Casino**
  - `READY`: The casino helper is idle and waiting for input.
  - `RUNNING`: The casino helper is currently processing a solve.

- **Cayo**
  - `READY`: The Cayo helper is idle and waiting for input.
  - `RUNNING`: The Cayo helper is currently processing a solve.

- **Kortz/Casino Keypad**
  - `READY`: The keypad solver is idle and waiting for input.
  - `3 LEFT`, `2 LEFT`, `1 LEFT`: The keypad solver is currently running and shows how many passes remain.

- **Nosave**
  - `VERIFYING`: Tessera is checking whether the firewall rule is working correctly during startup.
  - `ACTIVE`: Nosave is enabled and the firewall rule is active.
  - `INACTIVE`: Nosave is disabled.
  - `ERROR`: Nosave verification failed or the rule could not be validated.

- **Anti AFK**
  - `ACTIVE`: Anti AFK is enabled and the worker is running.
  - `INACTIVE`: Anti AFK is disabled.

The footer may also show an **update notice** when a newer release is available. The update notice is not a status row, but it is another terminal UI message that tells you where to open the release page.

### How to use the fingerprint helpers

Both helpers need to be positioned at the starting point of the puzzle. In short: when you begin, don't move the selector — then press the helper hotkey for each fingerprint.

- Make sure the tool is launched before you begin.

- Position the selector/cursor at the exact starting point of the puzzle and leave it there — do not move the selector during the puzzle.

- Begin and, when required, press the appropriate helper hotkey:
  - **F6**: Casino helper
  - **F7**: Cayo helper

- Press the helper hotkey for each fingerprint as it appears. The helper reads from the fixed selector position, so moving it will cause incorrect results.

- Test the helper once on your setup before relying on it. If it works once it should keep working unless you change system configuration or aspect ratio.

### How to use the keypad solver

- Start the keypad puzzle and leave the game window focused.

- Press `Shift + F6` once when the keypad sequence starts flashing.

- Do not press the hotkey again after each round. A single press starts the full solve cycle automatically.

- The solver detects the keypad mode on its own:
  - `4x5` for normal mode
  - `5x6` for hard mode

- After the first detection, Tessera continues the required passes automatically:
  - normal mode (`4x5`) runs 3 total passes
  - hard mode (`5x6`) runs 4 total passes

- The terminal status row `Kortz/Casino Keypad` will show how many passes are left while it is running.

- If you need to stop it manually, press `Shift + F6` again. `End` will also stop it because it exits the whole tool.


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
