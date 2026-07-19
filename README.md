<div align="center">

<img src="icon.ico" width="96" height="96" alt="Tessera"/>

# Tessera

**A tool to assist with GTAO Heists**

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

You can build the standalone GUI executable using PyInstaller with `--noconsole` (so no terminal window opens):

```bash
pyinstaller main.py `
  --onefile `
  --noconsole `
  --uac-admin `
  --icon=icon.ico `
  --name "Tessera" `
  --add-data "assets;assets"
```

Or build directly using the included spec file:
```bash
pyinstaller tessera.spec
```

## Tested resolutions (16:9)

- Supported aspect ratio: **16:9 only**. The tool was validated on the following resolutions:
  - 1600×900
  - 1920×1080 (Full HD)
  - 2560×1440 (QHD)

- Recommended setup:
  - Run the target application in **fullscreen**, **borderless fullscreen**, or **windowed** (borderless window preferred).
  - Set Windows display scaling to **100%** (DPI scaling can shift coordinates and break helpers).
  - Keep the tool's GUI window off the target display or minimized to the background.

- If your display is not 16:9 the helpers may be inaccurate. To troubleshoot:
  - Confirm the in-app resolution matches one of the tested values.
  - Confirm Windows scaling is 100% and that the target window is not overlapped by other windows.
  - If problems persist, try running the tool on a 16:9 display or report the issue with your resolution and scaling details.

## How to use the tool

### How to use the fingerprint helpers

Both helpers need to be positioned at the starting point of the hack. In short: when you start hacking, don't move the selector — then press the helper hotkey for each fingerprint.

- Make sure you have launched the tool before you begin the hack.

- Position the selector/cursor at the exact starting point of the fingerprint hack and leave it there — do not move the selector during the hack.

- Start the hack and, when required, press the appropriate helper hotkey:
  - **F6**: Casino fingerprint helper
  - **F7**: Cayo fingerprint helper

- Press the helper hotkey for each fingerprint as it appears. The helper reads from the fixed selector position, so moving it will cause incorrect results.

- Test the helper once before a critical heist to confirm it works on your setup. If it works once it should keep working unless you change system configuration or aspect ratio.


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

- The GUI dashboard status card and Debug Window (`CTRL + ALT + F8`) will show how many passes are left while it is running.

- If you need to stop it manually, press `Shift + F6` again. `End` will also stop it because it exits the whole tool.


### How to Use No Save (Current Method)

- Make sure you have launched the tool before starting your heist. While you can launch it during the heist, it's recommended to start it beforehand so you don't forget.

- Play the heist as you normally would. Make sure you've tested the tool at least once beforehand. You don't need to test it before every heist—if it worked once, it should continue working unless you've made changes to your system (such as installing antivirus software or modifying game/tool settings).

- When you toggle No Save with `F8`, you should see a small HUD banner in the top-right corner indicating its status:

  - `No Save ON` (green) when enabled.
  - `No Save OFF` (red) when disabled.

  If you don't see the banner, make sure the tool's dependencies are installed and that overlays aren't being blocked by other software.

- Play through the heist normally. Near the very end of the finale, just before completion, enable **No Save** with `F8`.

- After the heist finishes, you should see a **"Save Failed"** alert. This is expected and indicates that No Save is working correctly.

- Wait until all ending cutscenes have finished, you've received your payout, and you have full control of your GTA Online character again.

- Open the pause menu and go to **Online → Leave GTA Online** to return to Story Mode.

- Once Story Mode has fully loaded (make sure there are no loading indicators or spinning circles), disable **No Save** by pressing `F8`.

- Return to **GTA Online**, but **ONLY** join an **Invite Only** or **Friends Only** session. **DO NOT** join a public session at this stage.

- Once you've loaded into the private session, force the game to save by either:

  - Changing your outfit, **or**
  - Pressing **ALT+F4**.

  Wait until you see the **yellow loading circle** in the bottom-right corner and the **"Save Successful"** notification.

- After the save has completed successfully, leave GTA Online and return to **Story Mode** one more time. **Do not re-enable No Save** during this step.

- Finally, reconnect to **GTA Online** (again using an **Invite Only** or **Friends Only** session). Your payout should be saved while your heist progress and preps remain intact.


### How to use Job Warp

- Make sure the tool is running while you're in an Online session.
- Open the Pause Menu → Online → Options and set **Matchmaking** to **Closed**.
- In the Map hover over the **Job**  you want to teleport to.
- Press **F5** while the job is highlighted (make sure the start job option is visible in the bottom of the screen) to teleport to that job.


## License

This project is licensed under the **GNU General Public License v2.0** — see the [LICENSE](LICENSE) file for full terms.

## Disclaimer

For educational purposes only. The author/s are not responsible for any consequences including but not limited to account actions, data loss, or violations of terms of service.
