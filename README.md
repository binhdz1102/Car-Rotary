# AAOS Rotary Panel

A compact Python Tkinter panel for sending ADB `car_service` commands to simulate Android Automotive OS rotary input.

## Run

```bash
python ccp.py
```

## Controls

- Rotate left / right
- Tilt up / down / left / right
- Enter / center button

## Notes

- `ADB` can be `adb` if it is already in PATH, or the full path to `adb.exe` on Windows.
- `Serial` is optional when only one device is connected.
- `Repeat` sends the same command multiple times.
- `Delay ms` is the pause between repeated commands.
- `Check devices` runs `adb devices`.
