English | [简体中文](README.md)

# Keyboard-Overlay

A lightweight, highly customizable real-time keystroke display tool tailored for live streaming, tutorial recording, and esports broadcasts. Designed with a modern, minimalist, and professional esports aesthetic, discarding cluttered geek styles to provide viewers with the clearest and purest keystroke feedback experience.

## ✨ Highlights

*   **Modern Minimalist Aesthetic**: Professional esports-grade visual design with a clean and crisp interface.
*   **Transparent Desktop Overlay**: Global transparent floating layer with mouse passthrough support, ensuring zero interference with system operations.
*   **Advanced Control Console**: Built-in Web backend for visually adjusting key layouts, colors, trail directions, and auto-hide animations.
*   **Seamless OBS Integration**: Built-in independent local HTTP server; simply copy the link to use it as an OBS Browser Source.
*   **Portable Single File**: Packaged as a lightweight single EXE file with in-place persistence for configuration files, ensuring your settings are never lost.

## 🚀 How to Run

No complex installation or environment configuration required—truly out-of-the-box:

1. Place the packaged `KeyboardOverlay.exe` into any folder.
2. **Double-click `KeyboardOverlay.exe`** to launch.

> **Tip**: On its first run, the program will automatically extract `config.json` and `stats.json` into the same directory as the EXE to persistently save your custom layouts and keystroke statistics.

## 📦 How to Build

If you have modified the source code and wish to build the single EXE file yourself, follow these steps:

1. **Install Dependencies**:
   Ensure Python is installed on your computer, then run the following command in your terminal:
   ```bash
   pip install PySide6 websockets keyboard pyinstaller
   ```
2. **One-Click Build**:
   Double-click the `build.bat` batch script in the project's root directory.
3. **Get the Executable**:
   Once the build is complete, the new `.exe` file will be generated in the `dist` folder.

> **Platform Note**: This project relies on underlying APIs for global keyboard hooks and specific GUI transparent passthrough attributes. It is currently perfectly compatible with Windows.
