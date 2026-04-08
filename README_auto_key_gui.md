# Auto Key GUI 版说明

## 功能
- 简单界面，可调整每一步的按键和等待时间
- 可调整整轮执行周期（默认 15 秒）
- `Q` 全局热键可开始/暂停
- 开启/暂停有不同提示音
- 会把配置保存到 `auto_key_gui_config.json`

## 默认按键序列
1. `x`，等待 2 秒
2. `tab`，等待 1 秒
3. `2`，等待 3 秒
4. `esc`，等待 3 秒
5. `r`

## 运行
```bash
pip install -r requirements.txt
python auto_key_gui.py
```

## 打包为 Windows exe
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name auto_key_gui auto_key_gui.py
```

生成文件：
- `dist/auto_key_gui.exe`

## 注意
- 自动按键发送到当前前台窗口，请确保目标窗口在最前面。
- 某些高权限程序或游戏可能需要“以管理员身份运行”。
- `tab` 是 Tab 键，`esc` 是 Esc 键。
