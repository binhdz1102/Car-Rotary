# AAOS Rotary Control Panel

A compact Python Tkinter panel for simulating Android Automotive OS rotary input through ADB.

## Preview

![AAOS Rotary Panel](preview.png)

## Features

- Rotate left / right
- Tilt / nudge up, down, left, right
- Enter / center button
- Check connected ADB devices
- Repeat and delay controls
- Always-on-top floating window
- Vertically resizable panel while keeping the width compact

## Run

```bash
python ccp.py
```

## Notes

- Drag the bottom edge or bottom-right resize grip to change the panel height.
- The width is locked to keep the panel compact beside Android Studio or an emulator.
- Set `ADB` to a full adb path if `adb` is not available in PATH.