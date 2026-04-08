import json
import os
import platform
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import pydirectinput
except ImportError:
    pydirectinput = None

CONFIG_PATH = "auto_key_gui_enhanced_config.json"
DEFAULT_STEPS = [
    {"enabled": True, "key": "x", "hold": 0.08, "wait": 2.0},
    {"enabled": True, "key": "tab", "hold": 0.08, "wait": 1.0},
    {"enabled": True, "key": "2", "hold": 0.08, "wait": 3.0},
    {"enabled": True, "key": "esc", "hold": 0.08, "wait": 3.0},
    {"enabled": True, "key": "r", "hold": 0.08, "wait": 0.0},
]
DEFAULT_CONFIG = {
    "send_mode": "pydirectinput",
    "cycle_interval": 15.0,
    "startup_delay": 3.0,
    "steps": DEFAULT_STEPS,
}
SEND_MODES = ["pydirectinput", "keyboard"]


def beep_on():
    if platform.system().lower() == "windows":
        try:
            import winsound
            winsound.Beep(1200, 150)
            winsound.Beep(1600, 150)
            return
        except Exception:
            pass
    print("\a", end="", flush=True)


def beep_off():
    if platform.system().lower() == "windows":
        try:
            import winsound
            winsound.Beep(700, 220)
            return
        except Exception:
            pass
    print("\a", end="", flush=True)


class AutoKeyEnhancedApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Key Controller Enhanced")
        self.root.geometry("980x700")
        self.root.minsize(920, 620)

        self.log_queue = queue.Queue()
        self.running = False
        self.shutdown = False
        self.worker_thread = None
        self.hotkey_registered = False
        self.rows = []
        self.startup_delay_pending = True

        self.status_var = tk.StringVar(value="已暂停")
        self.hotkey_var = tk.StringVar(value="热键：Q")
        self.mode_var = tk.StringVar(value=DEFAULT_CONFIG["send_mode"])
        self.interval_var = tk.StringVar(value=str(DEFAULT_CONFIG["cycle_interval"]))
        self.startup_delay_var = tk.StringVar(value=str(DEFAULT_CONFIG["startup_delay"]))

        self._build_ui()
        self.load_config()
        self.register_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_log_queue)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")
        ttk.Label(top, text="状态：", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=(0, 16))
        ttk.Label(top, textvariable=self.hotkey_var).pack(side="left")

        ctrl = ttk.LabelFrame(main, text="控制", padding=10)
        ctrl.pack(fill="x", pady=(12, 10))

        ttk.Label(ctrl, text="发送模式").grid(row=0, column=0, sticky="w")
        mode_combo = ttk.Combobox(ctrl, textvariable=self.mode_var, values=SEND_MODES, width=18, state="readonly")
        mode_combo.grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Label(ctrl, text="每轮执行周期（秒）").grid(row=0, column=2, sticky="w")
        ttk.Entry(ctrl, textvariable=self.interval_var, width=10).grid(row=0, column=3, sticky="w", padx=(8, 16))

        ttk.Label(ctrl, text="启动前延迟（秒）").grid(row=0, column=4, sticky="w")
        ttk.Entry(ctrl, textvariable=self.startup_delay_var, width=10).grid(row=0, column=5, sticky="w", padx=(8, 16))

        ttk.Button(ctrl, text="开始 / 暂停", command=self.toggle_running).grid(row=0, column=6, padx=6)
        ttk.Button(ctrl, text="保存配置", command=self.save_config).grid(row=0, column=7, padx=6)
        ttk.Button(ctrl, text="恢复默认", command=self.reset_defaults).grid(row=0, column=8, padx=6)

        tips = (
            "建议先用记事本测试，再切到游戏测试。pydirectinput 通常比 keyboard 更适合部分游戏窗口。"
            "\n每步会执行：按下按键 → 按住指定秒数 → 松开 → 等待该步后的秒数。按 Q 可随时暂停。"
        )
        ttk.Label(ctrl, text=tips, foreground="#555555").grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))

        seq = ttk.LabelFrame(main, text="按键序列", padding=10)
        seq.pack(fill="both", expand=False, pady=(0, 10))

        header = ttk.Frame(seq)
        header.pack(fill="x")
        columns = [
            ("启用", 8),
            ("步骤", 6),
            ("按键名", 18),
            ("按住时长（秒）", 16),
            ("该步后等待（秒）", 16),
            ("操作", 8),
        ]
        for idx, (text, width) in enumerate(columns):
            ttk.Label(header, text=text, width=width, font=("Segoe UI", 10, "bold")).grid(row=0, column=idx, padx=4, pady=2, sticky="w")

        self.rows_frame = ttk.Frame(seq)
        self.rows_frame.pack(fill="x", pady=(4, 0))

        action_bar = ttk.Frame(seq)
        action_bar.pack(fill="x", pady=(10, 0))
        ttk.Button(action_bar, text="新增步骤", command=self.add_row).pack(side="left")
        ttk.Button(action_bar, text="清空步骤", command=self.clear_rows).pack(side="left", padx=(8, 0))
        ttk.Label(
            action_bar,
            text="常用按键名：x, tab, esc, enter, space, up, down, left, right, 1-9, f1-f12",
            foreground="#555555",
        ).pack(side="left", padx=(16, 0))

        log_frame = ttk.LabelFrame(main, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=16, wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.configure(state="disabled")

        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

    def append_log(self, message: str):
        now = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{now}] {message}\n")

    def process_log_queue(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        if not self.shutdown:
            self.root.after(100, self.process_log_queue)

    def add_row(self, step=None):
        if step is None:
            step = {"enabled": True, "key": "", "hold": 0.08, "wait": 0.0}

        row_index = len(self.rows)
        row_frame = ttk.Frame(self.rows_frame)
        row_frame.pack(fill="x", pady=2)

        enabled_var = tk.BooleanVar(value=bool(step.get("enabled", True)))
        key_var = tk.StringVar(value=str(step.get("key", "")))
        hold_var = tk.StringVar(value=str(step.get("hold", 0.08)))
        wait_var = tk.StringVar(value=str(step.get("wait", 0.0)))

        ttk.Checkbutton(row_frame, variable=enabled_var).grid(row=0, column=0, padx=4, sticky="w")
        order_label = ttk.Label(row_frame, text=str(row_index + 1), width=6)
        order_label.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Entry(row_frame, textvariable=key_var, width=18).grid(row=0, column=2, padx=4, sticky="w")
        ttk.Entry(row_frame, textvariable=hold_var, width=16).grid(row=0, column=3, padx=4, sticky="w")
        ttk.Entry(row_frame, textvariable=wait_var, width=16).grid(row=0, column=4, padx=4, sticky="w")
        ttk.Button(row_frame, text="删除", command=lambda rf=row_frame: self.remove_row(rf)).grid(row=0, column=5, padx=4, sticky="w")

        self.rows.append(
            {
                "frame": row_frame,
                "enabled_var": enabled_var,
                "key_var": key_var,
                "hold_var": hold_var,
                "wait_var": wait_var,
                "order_label": order_label,
            }
        )
        self.refresh_row_numbers()

    def remove_row(self, row_frame):
        target = None
        for row in self.rows:
            if row["frame"] is row_frame:
                target = row
                break
        if target is None:
            return
        target["frame"].destroy()
        self.rows.remove(target)
        self.refresh_row_numbers()

    def clear_rows(self):
        for row in list(self.rows):
            row["frame"].destroy()
        self.rows.clear()
        self.append_log("已清空全部步骤")

    def refresh_row_numbers(self):
        for idx, row in enumerate(self.rows, start=1):
            row["order_label"].configure(text=str(idx))

    def load_config(self):
        config = DEFAULT_CONFIG
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as exc:
                self.append_log(f"读取配置失败，已使用默认配置：{exc}")
                config = DEFAULT_CONFIG

        self.mode_var.set(config.get("send_mode", DEFAULT_CONFIG["send_mode"]))
        self.interval_var.set(str(config.get("cycle_interval", DEFAULT_CONFIG["cycle_interval"])))
        self.startup_delay_var.set(str(config.get("startup_delay", DEFAULT_CONFIG["startup_delay"])))

        self.clear_rows()
        steps = config.get("steps", DEFAULT_STEPS)
        for step in steps:
            self.add_row(step)
        if not steps:
            for step in DEFAULT_STEPS:
                self.add_row(step)

    def collect_config(self):
        send_mode = self.mode_var.get().strip().lower()
        if send_mode not in SEND_MODES:
            raise ValueError(f"发送模式无效：{send_mode}")

        try:
            cycle_interval = float(self.interval_var.get().strip())
            if cycle_interval <= 0:
                raise ValueError("必须大于 0")
        except Exception as exc:
            raise ValueError(f"每轮执行周期无效：{exc}")

        try:
            startup_delay = float(self.startup_delay_var.get().strip() or "0")
            if startup_delay < 0:
                raise ValueError("不能为负数")
        except Exception as exc:
            raise ValueError(f"启动前延迟无效：{exc}")

        steps = []
        for idx, row in enumerate(self.rows, start=1):
            enabled = bool(row["enabled_var"].get())
            key = row["key_var"].get().strip()
            if not key:
                if enabled:
                    raise ValueError(f"第 {idx} 步启用了但按键名为空")
                continue
            try:
                hold = float(row["hold_var"].get().strip() or "0")
                if hold < 0:
                    raise ValueError("不能为负数")
            except Exception as exc:
                raise ValueError(f"第 {idx} 步按住时长无效：{exc}")
            try:
                wait = float(row["wait_var"].get().strip() or "0")
                if wait < 0:
                    raise ValueError("不能为负数")
            except Exception as exc:
                raise ValueError(f"第 {idx} 步等待时间无效：{exc}")
            steps.append({"enabled": enabled, "key": key, "hold": hold, "wait": wait})

        active_steps = [s for s in steps if s["enabled"]]
        if not active_steps:
            raise ValueError("至少保留一个启用状态的步骤")

        return {
            "send_mode": send_mode,
            "cycle_interval": cycle_interval,
            "startup_delay": startup_delay,
            "steps": steps,
        }

    def save_config(self):
        try:
            config = self.collect_config()
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.append_log(f"配置已保存到 {CONFIG_PATH}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def reset_defaults(self):
        self.mode_var.set(DEFAULT_CONFIG["send_mode"])
        self.interval_var.set(str(DEFAULT_CONFIG["cycle_interval"]))
        self.startup_delay_var.set(str(DEFAULT_CONFIG["startup_delay"]))
        self.clear_rows()
        for step in DEFAULT_STEPS:
            self.add_row(step)
        self.append_log("已恢复默认配置")

    def register_hotkey(self):
        if keyboard is None:
            self.hotkey_var.set("热键：未启用（缺少 keyboard 库）")
            self.append_log("未安装 keyboard 库，Q 全局热键不可用，但界面按钮仍可控制。")
            return
        try:
            keyboard.add_hotkey("q", self.toggle_running)
            self.hotkey_registered = True
            self.append_log("已注册全局热键 Q")
        except Exception as exc:
            self.hotkey_var.set("热键：注册失败")
            self.append_log(f"全局热键注册失败：{exc}")

    def toggle_running(self):
        if self.shutdown:
            return
        self.running = not self.running
        if self.running:
            self.status_var.set("运行中")
            self.startup_delay_pending = True
            self.append_log("已启动自动按键")
            beep_on()
            if self.worker_thread is None or not self.worker_thread.is_alive():
                self.worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
                self.worker_thread.start()
        else:
            self.status_var.set("已暂停")
            self.append_log("已暂停自动按键")
            beep_off()

    def interruptible_sleep(self, seconds: float):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.shutdown or not self.running:
                return False
            time.sleep(min(0.05, max(0.0, end_time - time.time())))
        return True

    def send_key(self, key_name: str, hold_seconds: float, send_mode: str):
        send_mode = send_mode.lower()
        key_name = key_name.lower().strip()

        if send_mode == "pydirectinput":
            if pydirectinput is None:
                raise RuntimeError("缺少 pydirectinput 库，无法使用该发送模式")
            pydirectinput.FAILSAFE = False
            pydirectinput.PAUSE = 0
            pydirectinput.keyDown(key_name)
            if hold_seconds > 0:
                if not self.interruptible_sleep(hold_seconds):
                    return False
            pydirectinput.keyUp(key_name)
            return True

        if send_mode == "keyboard":
            if keyboard is None:
                raise RuntimeError("缺少 keyboard 库，无法使用该发送模式")
            keyboard.press(key_name)
            if hold_seconds > 0:
                if not self.interruptible_sleep(hold_seconds):
                    return False
            keyboard.release(key_name)
            return True

        raise RuntimeError(f"未知发送模式：{send_mode}")

    def worker_loop(self):
        while not self.shutdown:
            if not self.running:
                time.sleep(0.1)
                continue

            try:
                config = self.collect_config()
            except Exception as exc:
                self.append_log(f"配置错误，已自动暂停：{exc}")
                self.running = False
                self.status_var.set("已暂停")
                beep_off()
                time.sleep(0.1)
                continue

            if self.startup_delay_pending and config["startup_delay"] > 0:
                self.append_log(f"启动前延迟 {config['startup_delay']:.2f} 秒，请切到目标窗口")
                ok = self.interruptible_sleep(config["startup_delay"])
                if not ok:
                    continue
            self.startup_delay_pending = False

            cycle_start = time.time()
            active_steps = [s for s in config["steps"] if s["enabled"]]
            self.append_log(f"开始执行一轮，发送模式：{config['send_mode']}")

            for step in active_steps:
                if self.shutdown or not self.running:
                    break
                key_name = step["key"]
                hold_seconds = step["hold"]
                wait_seconds = step["wait"]
                try:
                    ok = self.send_key(key_name, hold_seconds, config["send_mode"])
                    if not ok:
                        break
                    self.append_log(f"已按下：{key_name}，按住 {hold_seconds:.2f} 秒")
                except Exception as exc:
                    self.append_log(f"发送按键失败（{key_name}）：{exc}")
                    self.running = False
                    self.status_var.set("已暂停")
                    beep_off()
                    break

                if wait_seconds > 0:
                    ok = self.interruptible_sleep(wait_seconds)
                    if not ok:
                        break

            if self.shutdown:
                break
            if not self.running:
                continue

            elapsed = time.time() - cycle_start
            remaining = max(0.0, config["cycle_interval"] - elapsed)
            self.append_log(f"本轮完成，耗时 {elapsed:.2f} 秒；距下一轮 {remaining:.2f} 秒")
            if remaining > 0:
                self.interruptible_sleep(remaining)

    def on_close(self):
        self.shutdown = True
        self.running = False
        try:
            if self.hotkey_registered and keyboard is not None:
                keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        pass
    app = AutoKeyEnhancedApp(root)
    root.mainloop()
