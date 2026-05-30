"""
AAOS Rotary Control Panel

A compact always-on-top Tkinter dashboard that sends ADB commands to simulate
an Android Automotive OS rotary controller.

Features:
- Nudge left, right, up, down
- Rotate counterclockwise / clockwise
- Center button
- Home and Back buttons
- Device screenshot capture to the computer Downloads folder using adb pull
- Custom command runner loaded from comands.txt / commands.txt
- Optional Always on top mode
- Vertically resizable window
- Windows console hiding support

Requirements:
- Python 3 with tkinter
- adb available in PATH, or set the full adb path in the UI
- An Android Automotive OS emulator/device connected and authorized
"""

from __future__ import annotations

import ctypes
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk

APP_DIR = Path(__file__).resolve().parent
CUSTOM_COMMAND_PRIMARY_FILE = "comands.txt"  # Kept as requested by the user.
CUSTOM_COMMAND_FALLBACK_FILE = "commands.txt"

# AAOS car_service commands and Android key events.
COMMANDS = {
    "rotate_left": ["shell", "cmd", "car_service", "inject-rotary"],
    "rotate_right": ["shell", "cmd", "car_service", "inject-rotary", "-c", "true"],
    "tilt_up": ["shell", "cmd", "car_service", "inject-key", "280"],
    "tilt_down": ["shell", "cmd", "car_service", "inject-key", "281"],
    "tilt_left": ["shell", "cmd", "car_service", "inject-key", "282"],
    "tilt_right": ["shell", "cmd", "car_service", "inject-key", "283"],
    "enter": ["shell", "cmd", "car_service", "inject-key", "23"],
    "home": ["shell", "input", "keyevent", "3"],
    "back": ["shell", "input", "keyevent", "4"],
}

ICONS = {
    "rotate_left": "left_rotation.png",
    "rotate_right": "right_rotation.png",
    "tilt_up": "up_arrow.png",
    "tilt_down": "down_arrow.png",
    "tilt_left": "left_arrow.png",
    "tilt_right": "right_arrow.png",
    "enter": "enter.png",
    "home": "home_button.png",
    "back": "back_button.png",
    "screenshot": "screen_shot.png",
}

ACTION_NAMES = {
    "rotate_left": "Rotate left",
    "rotate_right": "Rotate right",
    "tilt_up": "Tilt up",
    "tilt_down": "Tilt down",
    "tilt_left": "Tilt left",
    "tilt_right": "Tilt right",
    "enter": "Enter",
    "home": "Home",
    "back": "Back",
    "screenshot": "Screenshot",
}

TOOLTIPS = {
    "rotate_left": "Rotate counterclockwise",
    "rotate_right": "Rotate clockwise",
    "tilt_up": "Nudge up",
    "tilt_down": "Nudge down",
    "tilt_left": "Nudge left",
    "tilt_right": "Nudge right",
    "enter": "Center button",
    "home": "Home button",
    "back": "Back button",
    "screenshot": "Capture device screenshot to Downloads",
}


SAMPLE_COMMANDS_TEXT = """adb shell dumpsys window
adb shell dumpsys meminfo
adb devices
"""


def hide_console_window() -> None:
    """Hide the console window on Windows when the script is launched with python.exe."""
    if not sys.platform.startswith("win"):
        return
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, 0)
    except Exception:
        # The GUI should still open even if the console cannot be hidden.
        pass


def subprocess_no_window_options() -> dict[str, object]:
    """Return subprocess options that prevent child console windows on Windows."""
    if not sys.platform.startswith("win"):
        return {}

    options: dict[str, object] = {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    options["startupinfo"] = startupinfo

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if create_no_window:
        options["creationflags"] = create_no_window

    return options


class RotaryControlPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AAOS Rotary Panel")
        self.geometry("500x520")
        self.minsize(500, 420)
        # Allow changing only the vertical size. Width stays compact.
        self.resizable(False, True)

        self.icons: dict[str, tk.PhotoImage] = {}
        self.adb_path_var = tk.StringVar(value="adb")
        self.serial_var = tk.StringVar(value="")
        self.repeat_var = tk.IntVar(value=1)
        self.delay_ms_var = tk.IntVar(value=80)
        self.always_on_top_var = tk.BooleanVar(value=True)
        self.last_command_var = tk.StringVar(value="Ready")
        self.custom_command_var = tk.StringVar(value="")
        self.custom_commands: list[str] = []
        self.command_file_path = self._resolve_command_file_path()

        self._configure_style()
        self._build_ui()
        self._load_custom_commands(show_log=False)
        self._apply_window_mode()
        self.bind("<Escape>", lambda _: self.destroy())

    def _configure_style(self) -> None:
        self.configure(bg="#151515")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#151515")
        style.configure("Panel.TFrame", background="#202020")
        style.configure("TLabel", background="#151515", foreground="#eeeeee", font=("Segoe UI", 8))
        style.configure("Title.TLabel", background="#151515", foreground="#ffffff", font=("Segoe UI", 13, "bold"))
        style.configure("Hint.TLabel", background="#151515", foreground="#bbbbbb", font=("Segoe UI", 8))
        style.configure("Panel.TLabel", background="#202020", foreground="#eeeeee", font=("Segoe UI", 8))
        style.configure("Panel.TCheckbutton", background="#202020", foreground="#eeeeee", font=("Segoe UI", 8))
        style.map(
            "Panel.TCheckbutton",
            background=[("active", "#202020")],
            foreground=[("active", "#ffffff")],
        )
        style.configure("TButton", font=("Segoe UI", 8, "bold"), padding=4)
        style.configure("Icon.TButton", padding=3)
        style.configure("TEntry", padding=3)
        style.configure("TSpinbox", padding=3)
        style.configure("TCombobox", padding=3)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="AAOS Rotary Panel", style="Title.TLabel")
        title.pack(anchor="w")

        hint = ttk.Label(
            root,
            text="ADB simulator for AAOS rotary input.",
            style="Hint.TLabel",
        )
        hint.pack(anchor="w", pady=(1, 7))

        config = ttk.Frame(root, style="Panel.TFrame", padding=7)
        config.pack(fill="x", pady=(0, 8))

        ttk.Label(config, text="ADB", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        ttk.Entry(config, textvariable=self.adb_path_var, width=18).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=2)

        ttk.Label(config, text="Serial", style="Panel.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 5), pady=2)
        ttk.Entry(config, textvariable=self.serial_var, width=18).grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=2)

        ttk.Button(config, text="Check devices", command=self.check_devices).grid(row=0, column=4, sticky="ew", pady=2)

        ttk.Label(config, text="Repeat", style="Panel.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=2)
        ttk.Spinbox(config, from_=1, to=100, textvariable=self.repeat_var, width=5).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(config, text="Delay ms", style="Panel.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=2)
        ttk.Spinbox(config, from_=0, to=2000, increment=10, textvariable=self.delay_ms_var, width=5).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Checkbutton(
            config,
            text="Always on top",
            variable=self.always_on_top_var,
            command=self._apply_window_mode,
            style="Panel.TCheckbutton",
        ).grid(row=1, column=4, sticky="w", pady=2)

        config.columnconfigure(1, weight=1)
        config.columnconfigure(3, weight=1)

        control = ttk.Frame(root, style="Panel.TFrame", padding=8)
        control.pack(anchor="center", pady=(0, 8))

        for c in range(5):
            control.columnconfigure(c, minsize=50)
        for r in range(3):
            control.rowconfigure(r, minsize=50)

        # Compact physical layout:
        #                 tilt up | screenshot
        # rotate left | tilt left | enter | tilt right | rotate right
        # back                  | tilt down | home
        self._add_icon_button(control, "tilt_up", 0, 2)
        self._add_icon_button(control, "screenshot", 0, 3)
        self._add_icon_button(control, "rotate_left", 1, 0)
        self._add_icon_button(control, "tilt_left", 1, 1)
        self._add_icon_button(control, "enter", 1, 2)
        self._add_icon_button(control, "tilt_right", 1, 3)
        self._add_icon_button(control, "rotate_right", 1, 4)
        self._add_icon_button(control, "back", 2, 1)
        self._add_icon_button(control, "tilt_down", 2, 2)
        self._add_icon_button(control, "home", 2, 3)

        custom = ttk.Frame(root, style="Panel.TFrame", padding=7)
        custom.pack(fill="x", pady=(0, 8))

        ttk.Label(custom, text="Command file", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        ttk.Label(
            custom,
            textvariable=tk.StringVar(value=self.command_file_path.name),
            style="Panel.TLabel",
        ).grid(row=0, column=1, sticky="w", pady=2)

        ttk.Button(custom, text="Reload", command=lambda: self._load_custom_commands(show_log=True)).grid(
            row=0, column=2, sticky="ew", padx=(8, 4), pady=2
        )
        ttk.Button(custom, text="Run", command=self.run_selected_custom_command).grid(
            row=0, column=3, sticky="ew", padx=(4, 0), pady=2
        )

        self.custom_command_combo = ttk.Combobox(
            custom,
            textvariable=self.custom_command_var,
            values=[],
            state="readonly",
            width=52,
        )
        self.custom_command_combo.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(3, 2))
        custom.columnconfigure(1, weight=1)

        command_box = ttk.Frame(root, style="Panel.TFrame", padding=7)
        command_box.pack(fill="both", expand=True)

        ttk.Label(command_box, text="Last command", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(
            command_box,
            textvariable=self.last_command_var,
            background="#202020",
            foreground="#9be38f",
            font=("Consolas", 8),
        ).pack(anchor="w", pady=(1, 4))

        self.output = tk.Text(
            command_box,
            height=4,
            wrap="word",
            bg="#111111",
            fg="#eeeeee",
            insertbackground="#eeeeee",
            font=("Consolas", 8),
            relief="flat",
        )
        self.output.pack(fill="both", expand=True)

        bottom_bar = ttk.Frame(root, style="TFrame")
        bottom_bar.pack(fill="x", pady=(5, 0))
        ttk.Label(
            bottom_bar,
            text="Edit comands.txt, click Reload, choose a command, then Run.",
            style="Hint.TLabel",
        ).pack(side="left")
        ttk.Sizegrip(bottom_bar).pack(side="right", anchor="se")

        self._append_output("Ready. Connect an AAOS emulator/device, then click a button.\n")

    def _apply_window_mode(self) -> None:
        is_topmost = bool(self.always_on_top_var.get())

        # Keep the panel floating above Android Studio / Emulator when enabled.
        self.attributes("-topmost", is_topmost)

        # Windows-only: make the panel look like a small floating tool window.
        if sys.platform.startswith("win"):
            try:
                self.attributes("-toolwindow", True)
            except tk.TclError:
                pass

        if is_topmost:
            self.lift()

    def _load_icon(self, key: str) -> tk.PhotoImage | None:
        icon_path = APP_DIR / ICONS[key]
        if not icon_path.exists():
            return None
        image = tk.PhotoImage(file=str(icon_path))
        max_dim = max(image.width(), image.height())
        factor = max(1, round(max_dim / 36))
        if factor > 1:
            image = image.subsample(factor, factor)
        self.icons[key] = image
        return image

    def _add_icon_button(self, parent: ttk.Frame, key: str, row: int, column: int) -> None:
        icon = self._load_icon(key)

        if key == "screenshot":
            command = self.take_screenshot
        else:
            command = lambda k=key: self.send_rotary_command(k)

        button = ttk.Button(
            parent,
            text="" if icon else ACTION_NAMES[key],
            image=icon,
            compound="center" if icon else "none",
            style="Icon.TButton",
            command=command,
        )
        button.grid(row=row, column=column, sticky="nsew", padx=3, pady=3, ipadx=0, ipady=0)
        button.configure(width=4)
        self._add_tooltip(button, TOOLTIPS[key])

    def _add_tooltip(self, widget: tk.Widget, text: str) -> None:
        tooltip: dict[str, tk.Toplevel | None] = {"window": None}

        def show(_: tk.Event) -> None:
            if tooltip["window"] is not None:
                return
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 3
            window = tk.Toplevel(widget)
            window.wm_overrideredirect(True)
            window.wm_geometry(f"+{x}+{y}")
            try:
                window.attributes("-topmost", True)
            except tk.TclError:
                pass
            label = tk.Label(window, text=text, bg="#303030", fg="#eeeeee", padx=6, pady=3, font=("Segoe UI", 8))
            label.pack()
            tooltip["window"] = window

        def hide(_: tk.Event) -> None:
            window = tooltip["window"]
            if window is not None:
                window.destroy()
                tooltip["window"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _adb_base(self) -> list[str]:
        adb = self.adb_path_var.get().strip() or "adb"
        serial = self.serial_var.get().strip()
        base = [adb]
        if serial:
            base.extend(["-s", serial])
        return base

    def _resolve_command_file_path(self) -> Path:
        primary = APP_DIR / CUSTOM_COMMAND_PRIMARY_FILE
        fallback = APP_DIR / CUSTOM_COMMAND_FALLBACK_FILE
        if primary.exists():
            return primary
        if fallback.exists():
            return fallback
        return primary

    def _ensure_command_file(self) -> None:
        if self.command_file_path.exists():
            return
        self.command_file_path.write_text(SAMPLE_COMMANDS_TEXT, encoding="utf-8")

    def _load_custom_commands(self, show_log: bool) -> None:
        self.command_file_path = self._resolve_command_file_path()
        try:
            self._ensure_command_file()
            lines = self.command_file_path.read_text(encoding="utf-8").splitlines()
            commands = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
            self.custom_commands = commands
            self.custom_command_combo.configure(values=commands)
            if commands:
                current = self.custom_command_var.get().strip()
                if current not in commands:
                    self.custom_command_var.set(commands[0])
            else:
                self.custom_command_var.set("")
            if show_log:
                self._append_output(f"Loaded {len(commands)} custom command(s) from {self.command_file_path.name}.\n")
        except OSError as error:
            self.custom_commands = []
            self.custom_command_combo.configure(values=[])
            self.custom_command_var.set("")
            if show_log:
                self._append_output(f"Failed to read {self.command_file_path.name}: {error}\n")

    @staticmethod
    def _looks_like_adb_executable(token: str) -> bool:
        normalized = token.strip('"').replace("\\", "/")
        name = normalized.rsplit("/", 1)[-1].lower()
        return name in {"adb", "adb.exe"}

    def _build_custom_command(self, command_line: str) -> list[str]:
        try:
            tokens = shlex.split(command_line, comments=False, posix=True)
        except ValueError as error:
            raise ValueError(f"Invalid command syntax: {error}") from error

        if not tokens:
            raise ValueError("No command selected.")

        if self._looks_like_adb_executable(tokens[0]):
            adb = self.adb_path_var.get().strip() or tokens[0]
            rest = tokens[1:]
            if rest and rest[0] == "devices":
                # 'adb devices' should list every device, so it should not be narrowed by -s SERIAL.
                return [adb] + rest
            base = [adb]
            serial = self.serial_var.get().strip()
            if serial:
                base.extend(["-s", serial])
            return base + rest

        return tokens

    def run_selected_custom_command(self) -> None:
        command_line = self.custom_command_var.get().strip()
        if not command_line:
            self._append_output("No custom command selected. Edit comands.txt, then click Reload.\n")
            return

        try:
            cmd = self._build_custom_command(command_line)
        except ValueError as error:
            self._append_output(str(error) + "\n")
            return

        self._run_command_async(cmd, f"Custom: {command_line}", repeat=1, delay_ms=0, timeout=45)

    def check_devices(self) -> None:
        cmd = [self.adb_path_var.get().strip() or "adb", "devices"]
        self._run_command_async(cmd, "Check devices", repeat=1, delay_ms=0)

    def send_rotary_command(self, key: str) -> None:
        repeat = max(1, int(self.repeat_var.get()))
        delay_ms = max(0, int(self.delay_ms_var.get()))
        cmd = self._adb_base() + COMMANDS[key]
        self._run_command_async(cmd, ACTION_NAMES[key], repeat=repeat, delay_ms=delay_ms)

    def take_screenshot(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"aaos_screenshot_{timestamp}.png"
        downloads_dir = Path.home() / "Downloads"
        screenshot_path = downloads_dir / filename
        remote_path = f"/sdcard/Download/{filename}"

        self.last_command_var.set(f"screencap -> adb pull -> {screenshot_path}")
        self._append_output(
            "\n▶ Screenshot\n"
            f"$ {' '.join(self._adb_base() + ['shell', 'screencap', '-p', remote_path])}\n"
            f"$ {' '.join(self._adb_base() + ['pull', remote_path, str(screenshot_path)])}\n"
        )

        thread = threading.Thread(
            target=self._screenshot_worker,
            args=(remote_path, screenshot_path),
            daemon=True,
        )
        thread.start()

    def _run_process_for_screenshot(self, cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **subprocess_no_window_options(),
        )

    @staticmethod
    def _is_valid_png(path: Path) -> bool:
        try:
            if not path.exists() or path.stat().st_size < 8:
                return False
            with path.open("rb") as file:
                return file.read(8) == b"\x89PNG\r\n\x1a\n"
        except OSError:
            return False

    def _screenshot_worker(self, remote_path: str, screenshot_path: Path) -> None:
        try:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            adb = self._adb_base()

            # More reliable than streaming PNG bytes through stdout on Windows.
            # First write a real PNG file on the device, then pull that file to Downloads.
            capture = self._run_process_for_screenshot(adb + ["shell", "screencap", "-p", remote_path])
            if capture.returncode != 0:
                error = capture.stderr.strip() or capture.stdout.strip()
                message = error or f"Screenshot failed. Exit code: {capture.returncode}"
                self.after(0, lambda: self._append_output(message + "\n"))
                return

            pull = self._run_process_for_screenshot(adb + ["pull", remote_path, str(screenshot_path)])

            # Clean up the temporary screenshot on the Android device.
            self._run_process_for_screenshot(adb + ["shell", "rm", "-f", remote_path], timeout=8)

            if pull.returncode != 0:
                error = pull.stderr.strip() or pull.stdout.strip()
                try:
                    screenshot_path.unlink(missing_ok=True)
                except OSError:
                    pass
                message = error or f"adb pull failed. Exit code: {pull.returncode}"
            elif self._is_valid_png(screenshot_path):
                message = f"Saved screenshot to: {screenshot_path}"
            else:
                try:
                    screenshot_path.unlink(missing_ok=True)
                except OSError:
                    pass
                message = "Screenshot failed. The pulled file was not a valid PNG."
        except FileNotFoundError:
            message = "adb not found. Set the full adb path or add adb to PATH."
        except subprocess.TimeoutExpired:
            message = "Screenshot timeout. Check the emulator/device and authorization state."
        except OSError as error:
            message = f"Screenshot failed: {error}"

        self.after(0, lambda: self._append_output(message + "\n"))

    def _run_command_async(self, cmd: list[str], label: str, repeat: int, delay_ms: int, timeout: int = 12) -> None:
        self.last_command_var.set(" ".join(cmd))
        self._append_output(f"\n▶ {label}\n$ {' '.join(cmd)}\n")
        thread = threading.Thread(target=self._run_command_worker, args=(cmd, repeat, delay_ms, timeout), daemon=True)
        thread.start()

    def _run_command_worker(self, cmd: list[str], repeat: int, delay_ms: int, timeout: int) -> None:
        outputs: list[str] = []
        for index in range(repeat):
            try:
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    **subprocess_no_window_options(),
                )
                if completed.stdout.strip():
                    outputs.append(completed.stdout.strip())
                if completed.stderr.strip():
                    outputs.append(completed.stderr.strip())
                if completed.returncode != 0:
                    outputs.append(f"Exit code: {completed.returncode}")
                    break
            except FileNotFoundError:
                outputs.append("adb not found. Set the full adb path or add adb to PATH.")
                break
            except subprocess.TimeoutExpired:
                outputs.append("Command timeout. Check the emulator/device and authorization state.")
                break

            if index < repeat - 1 and delay_ms > 0:
                time.sleep(delay_ms / 1000)

        if not outputs:
            outputs.append("OK")
        self.after(0, lambda: self._append_output("\n".join(outputs) + "\n"))

    def _append_output(self, text: str) -> None:
        self.output.insert("end", text)
        self.output.see("end")


def main() -> None:
    hide_console_window()
    app = RotaryControlPanel()
    app.mainloop()


if __name__ == "__main__":
    main()
