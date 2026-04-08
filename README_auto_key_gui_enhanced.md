# Auto Key GUI Enhanced

这是增强版 Windows 自动按键 GUI，适合先在普通窗口测试，再在部分游戏窗口中尝试。

## 主要增强点

- 发送模式可切换：`pydirectinput` / `keyboard`
- 每一步可单独设置：
  - 是否启用
  - 按键名
  - 按住时长
  - 该步后等待时间
- 支持新增、删除步骤
- 支持启动前延迟，便于切回目标窗口
- `Q` 作为全局开始/暂停热键
- 配置自动保存到 `auto_key_gui_enhanced_config.json`

## 安装

```bash
pip install -r requirements_enhanced.txt
```

## 运行

```bash
python auto_key_gui_enhanced.py
```

## 打包为 Windows EXE

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name auto_key_gui_enhanced auto_key_gui_enhanced.py
```

生成文件：

```text
dist/auto_key_gui_enhanced.exe
```

## 使用建议

1. 先把发送模式设为 `pydirectinput`
2. 启动前延迟设为 3 秒以上
3. 先在记事本测试键序
4. 再切到游戏窗口测试
5. 若游戏是独占全屏，可优先尝试无边框窗口化

## 常用按键名

- 字母数字：`x`, `r`, `2`
- 控制键：`tab`, `esc`, `enter`, `space`
- 方向键：`up`, `down`, `left`, `right`
- 功能键：`f1` 到 `f12`

## 注意

- 部分游戏不会接收普通桌面合成输入
- 这类情况下，切换到 `pydirectinput` 往往比 `keyboard` 更值得先试
- 若目标程序没有焦点，按键通常不会送达
