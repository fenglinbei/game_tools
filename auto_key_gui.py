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

CONFIG_PATH = "auto_key_gui_config.json"
DEFAULT_STEPS = [
    {"key": "x", "wait": 2.0},
    {"key": "tab", "wait": 1.0},
    {"key": "2", "wait": 3.0},
    {"key": "esc", "wait": 3.0},
    {"key": "r", "wait": 0.0},
]
DEFAULT_CONFIG = {
    "cycle_interval": 15.0,
    "steps": DEFAULT_STEPS,
}


def beep_on():
    if platform.system().lower() == "windows":
        try:
            import winsound
            winsound.Beep(1200, 180)
            winsound.Beep(1600, 180)
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


class AutoKeyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Auto Key Controller")
        self.root.geometry("760x520")
        self.root.minsize(720, 500)

        self.log_queue = queue.Queue()
        self.running = False
        self.shutdown = False
        self.worker_thread = None
        self.hotkey_registered = False
        self.steps_vars = []

        self.status_var = tk.StringVar(value="已暂停")
        self.hotkey_var = tk.StringVar(value="热键：Q")
        self.interval_var = tk.StringVar(value=str(DEFAULT_CONFIG["cycle_interval"]))

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
        self.status_label = ttk.Label(top, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(0, 16))

        ttk.Label(top, textvariable=self.hotkey_var).pack(side="left")

        ctrl = ttk.LabelFrame(main, text="控制", padding=10)
        ctrl.pack(fill="x", pady=(12, 10))

        ttk.Label(ctrl, text="每轮执行周期（秒）").grid(row=0, column=0, sticky="w")
        ttk.Entry(ctrl, textvariable=self.interval_var, width=12).grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Button(ctrl, text="开始 / 暂停", command=self.toggle_running).grid(row=0, column=2, padx=6)
        ttk.Button(ctrl, text="保存配置", command=self.save_config).grid(row=0, column=3, padx=6)
        ttk.Button(ctrl, text="恢复默认", command=self.reset_defaults).grid(row=0, column=4, padx=6)

        tips = (
            "说明：按 Q 可全局开始/暂停。每轮会按顺序发送下方按键，并在每步后等待指定秒数。"
            "\n周期按“整轮起点到下一轮起点”的间隔计算；若单轮耗时超过周期，则完成后立即进入下一轮。"
        )
        ttk.Label(ctrl, text=tips, foreground="#555555").grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))

        seq = ttk.LabelFrame(main, text="按键序列", padding=10)
        seq.pack(fill="x", pady=(0, 10))

        headers = ["步骤", "按键名", "该步后等待（秒）"]
        for col, text in enumerate(headers):
            ttk.Label(seq, text=text, font=("Segoe UI", 10, "bold")).grid(row=0, column=col, padx=8, pady=4, sticky="w")

        for i in range(5):
            step_no = ttk.Label(seq, text=f"{i + 1}")
            step_no.grid(row=i + 1, column=0, padx=8, pady=4, sticky="w")

            key_var = tk.StringVar()
            wait_var = tk.StringVar()
            self.steps_vars.append((key_var, wait_var))

            ttk.Entry(seq, textvariable=key_var, width=18).grid(row=i + 1, column=1, padx=8, pady=4, sticky="w")
            ttk.Entry(seq, textvariable=wait_var, width=18).grid(row=i + 1, column=2, padx=8, pady=4, sticky="w")

        examples = (
            "常用按键名示例：x, tab, 2, esc, r, enter, space, up, down, left, right"
        )
        ttk.Label(seq, text=examples, foreground="#555555").grid(row=6, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 0))

        log_frame = ttk.LabelFrame(main, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=14, wrap="word")
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

    def load_config(self):
        config = DEFAULT_CONFIG
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as exc:
                self.append_log(f"读取配置失败，已使用默认配置：{exc}")
                config = DEFAULT_CONFIG

        self.interval_var.set(str(config.get("cycle_interval", 15.0)))
        steps = config.get("steps", DEFAULT_STEPS)
        for i, (key_var, wait_var) in enumerate(self.steps_vars):
            if i < len(steps):
                key_var.set(str(steps[i].get("key", "")))
                wait_var.set(str(steps[i].get("wait", 0.0)))
            else:
                key_var.set("")
                wait_var.set("0")

    def collect_config(self):
        try:
            cycle_interval = float(self.interval_var.get().strip())
            if cycle_interval <= 0:
                raise ValueError("周期必须大于 0")
        except Exception as exc:
            raise ValueError(f"周期无效：{exc}")

        steps = []
        for idx, (key_var, wait_var) in enumerate(self.steps_vars, start=1):
            key = key_var.get().strip()
            if not key:
                continue
            try:
                wait = float(wait_var.get().strip() or "0")
                if wait < 0:
                    raise ValueError("不能为负数")
            except Exception as exc:
                raise ValueError(f"第 {idx} 步等待时间无效：{exc}")
            steps.append({"key": key, "wait": wait})

        if not steps:
            raise ValueError("至少保留一个按键步骤")

        return {"cycle_interval": cycle_interval, "steps": steps}

    def save_config(self):
        try:
            config = self.collect_config()
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.append_log(f"配置已保存到 {CONFIG_PATH}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def reset_defaults(self):
        self.interval_var.set(str(DEFAULT_CONFIG["cycle_interval"]))
        for i, (key_var, wait_var) in enumerate(self.steps_vars):
            key_var.set(DEFAULT_STEPS[i]["key"])
            wait_var.set(str(DEFAULT_STEPS[i]["wait"]))
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
            time.sleep(min(0.05, end_time - time.time()))
        return True

    def send_key(self, key_name: str):
        if keyboard is None:
            raise RuntimeError("缺少 keyboard 库，无法发送按键")
        keyboard.press_and_release(key_name)

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

            cycle_start = time.time()
            self.append_log("开始执行一轮")

            for step in config["steps"]:
                if self.shutdown or not self.running:
                    break
                key_name = step["key"]
                wait_seconds = step["wait"]
                try:
                    self.send_key(key_name)
                    self.append_log(f"已按下：{key_name}")
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
    app = AutoKeyApp(root)
    root.mainloop()
