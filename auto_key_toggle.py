import threading
import time
from datetime import datetime

import keyboard

# =========================
# 配置区
# =========================
INTERVAL_SECONDS = 15.0  # 每轮开始之间的间隔（按固定周期调度）
TOGGLE_HOTKEY = "q"      # 启动/暂停热键

# 按键序列： (按键名, 按下后等待秒数)
# 这里把用户写的 Tap 按 Tab 处理；若不是 Tab，把 "tab" 改成你需要的键名即可。
KEY_SEQUENCE = [
    ("x", 2.0),
    ("tab", 1.0),
    ("2", 3.0),
    ("esc", 3.0),
    ("r", 0.0),
]

# =========================
# 状态区
# =========================
_enabled = False
_state_lock = threading.Lock()
_next_run_time = None


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{now_str()}] {msg}", flush=True)


def beep_on() -> None:
    try:
        import winsound
        winsound.Beep(1200, 120)
        winsound.Beep(1600, 120)
    except Exception:
        print("\a", end="", flush=True)


def beep_off() -> None:
    try:
        import winsound
        winsound.Beep(700, 220)
    except Exception:
        print("\a", end="", flush=True)


def is_enabled() -> bool:
    with _state_lock:
        return _enabled


def set_enabled(value: bool) -> None:
    global _enabled, _next_run_time
    with _state_lock:
        _enabled = value
        # 切换为开启时，立即执行一轮
        _next_run_time = time.monotonic() if value else None


def toggle_enabled() -> None:
    new_value = not is_enabled()
    set_enabled(new_value)
    if new_value:
        beep_on()
        log("已开启自动控制。")
    else:
        beep_off()
        log("已暂停自动控制。")


def interruptible_sleep(seconds: float) -> bool:
    """
    可中断等待。
    返回 True 表示正常等待结束；
    返回 False 表示等待过程中已被暂停。
    """
    end_time = time.monotonic() + seconds
    while time.monotonic() < end_time:
        if not is_enabled():
            return False
        time.sleep(0.05)
    return True


def press_key(key_name: str) -> None:
    keyboard.press_and_release(key_name)
    log(f"发送按键：{key_name}")


def run_one_cycle() -> None:
    log("开始执行一轮动作。")
    for key_name, wait_seconds in KEY_SEQUENCE:
        if not is_enabled():
            log("检测到暂停，当前轮次已中止。")
            return

        press_key(key_name)

        if wait_seconds > 0:
            ok = interruptible_sleep(wait_seconds)
            if not ok:
                log("等待过程中检测到暂停，当前轮次已中止。")
                return

    log("本轮动作执行完成。")


def worker_loop() -> None:
    global _next_run_time
    log("脚本已启动。按 q 可开启/暂停；按 Ctrl+C 退出。")
    while True:
        if not is_enabled():
            time.sleep(0.1)
            continue

        with _state_lock:
            next_run = _next_run_time

        if next_run is None:
            with _state_lock:
                _next_run_time = time.monotonic()
            time.sleep(0.05)
            continue

        now = time.monotonic()
        if now < next_run:
            time.sleep(min(0.1, next_run - now))
            continue

        run_one_cycle()

        # 固定周期：每轮开始时间间隔为 15 秒
        with _state_lock:
            if _enabled:
                _next_run_time = next_run + INTERVAL_SECONDS
                # 如果由于卡顿/阻塞错过了周期，则从当前时间重新计时，避免连环补跑
                if _next_run_time < time.monotonic():
                    _next_run_time = time.monotonic() + INTERVAL_SECONDS
            else:
                _next_run_time = None


def main() -> None:
    # suppress=True: 按 q 时不再把 q 传递给前台程序
    # trigger_on_release=True: 在松开时触发，避免长按重复切换
    keyboard.add_hotkey(TOGGLE_HOTKEY, toggle_enabled, suppress=True, trigger_on_release=True)

    try:
        worker_loop()
    except KeyboardInterrupt:
        log("收到退出信号，脚本结束。")


if __name__ == "__main__":
    main()
