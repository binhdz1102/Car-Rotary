"""
AAOS Rotary Control Panel

A compact always-on-top Tkinter dashboard that sends ADB commands to simulate
an Android Automotive OS rotary controller.

Features:
- Nudge left, right, up, down
- Rotate counterclockwise / clockwise
- Center button
- Optional Always on top mode
- Vertically resizable window

Requirements:
- Python 3 with tkinter
- adb available in PATH, or set the full adb path in the UI
- An Android Automotive OS emulator/device connected and authorized
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk

APP_DIR = Path(__file__).resolve().parent

# AAOS car_service commands.
COMMANDS = {
    "rotate_left": ["shell", "cmd", "car_service", "inject-rotary"],
    "rotate_right": ["shell", "cmd", "car_service", "inject-rotary", "-c", "true"],
    "tilt_up": ["shell", "cmd", "car_service", "inject-key", "280"],
    "tilt_down": ["shell", "cmd", "car_service", "inject-key", "281"],
    "tilt_left": ["shell", "cmd", "car_service", "inject-key", "282"],
    "tilt_right": ["shell", "cmd", "car_service", "inject-key", "283"],
    "enter": ["shell", "cmd", "car_service", "inject-key", "23"],
}

ICONS = {
    "rotate_left": "left_rotation.png",
    "rotate_right": "right_rotation.png",
    "tilt_up": "up_arrow.png",
    "tilt_down": "down_arrow.png",
    "tilt_left": "left_arrow.png",
    "tilt_right": "right_arrow.png",
    "enter": "enter.png",
}

ACTION_NAMES = {
    "rotate_left": "Rotate left",
    "rotate_right": "Rotate right",
    "tilt_up": "Tilt up",
    "tilt_down": "Tilt down",
    "tilt_left": "Tilt left",
    "tilt_right": "Tilt right",
    "enter": "Enter",
}

TOOLTIPS = {
    "rotate_left": "Rotate counterclockwise",
    "rotate_right": "Rotate clockwise",
    "tilt_up": "Nudge up",
    "tilt_down": "Nudge down",
    "tilt_left": "Nudge left",
    "tilt_right": "Nudge right",
    "enter": "Center button",
}


class RotaryControlPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AAOS Rotary Panel")
        self.geometry("500x430")
        self.minsize(500, 330)
        # Allow changing only the vertical size. Width stays compact.
        self.resizable(False, True)

        self.icons: dict[str, tk.PhotoImage] = {}
        self.adb_path_var = tk.StringVar(value="adb")
        self.serial_var = tk.StringVar(value="")
        self.repeat_var = tk.IntVar(value=1)
        self.delay_ms_var = tk.IntVar(value=80)
        self.always_on_top_var = tk.BooleanVar(value=True)
        self.last_command_var = tk.StringVar(value="Ready")

        self._configure_style()
        self._build_ui()
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
            control.columnconfigure(c, minsize=58)
        for r in range(3):
            control.rowconfigure(r, minsize=58)

        # Compact physical layout:
        #               tilt up
        # rotate left | tilt left | enter | tilt right | rotate right
        #              tilt down
        self._add_icon_button(control, "tilt_up", 0, 2)
        self._add_icon_button(control, "rotate_left", 1, 0)
        self._add_icon_button(control, "tilt_left", 1, 1)
        self._add_icon_button(control, "enter", 1, 2)
        self._add_icon_button(control, "tilt_right", 1, 3)
        self._add_icon_button(control, "rotate_right", 1, 4)
        self._add_icon_button(control, "tilt_down", 2, 2)

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
            text="Drag the bottom edge to resize height.",
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
        factor = max(1, round(max_dim / 40))
        if factor > 1:
            image = image.subsample(factor, factor)
        self.icons[key] = image
        return image

    def _add_icon_button(self, parent: ttk.Frame, key: str, row: int, column: int) -> None:
        icon = self._load_icon(key)
        button = ttk.Button(
            parent,
            text="" if icon else ACTION_NAMES[key],
            image=icon,
            compound="center" if icon else "none",
            style="Icon.TButton",
            command=lambda k=key: self.send_rotary_command(k),
        )
        button.grid(row=row, column=column, sticky="nsew", padx=4, pady=4, ipadx=1, ipady=1)
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

    def check_devices(self) -> None:
        cmd = [self.adb_path_var.get().strip() or "adb", "devices"]
        self._run_command_async(cmd, "Check devices", repeat=1, delay_ms=0)

    def send_rotary_command(self, key: str) -> None:
        repeat = max(1, int(self.repeat_var.get()))
        delay_ms = max(0, int(self.delay_ms_var.get()))
        cmd = self._adb_base() + COMMANDS[key]
        self._run_command_async(cmd, ACTION_NAMES[key], repeat=repeat, delay_ms=delay_ms)

    def _run_command_async(self, cmd: list[str], label: str, repeat: int, delay_ms: int) -> None:
        self.last_command_var.set(" ".join(cmd))
        self._append_output(f"\n▶ {label}\n$ {' '.join(cmd)}\n")
        thread = threading.Thread(target=self._run_command_worker, args=(cmd, repeat, delay_ms), daemon=True)
        thread.start()

    def _run_command_worker(self, cmd: list[str], repeat: int, delay_ms: int) -> None:
        outputs: list[str] = []
        for index in range(repeat):
            try:
                completed = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
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


if __name__ == "__main__":
    app = RotaryControlPanel()
    app.mainloop()
