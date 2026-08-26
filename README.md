# 桌面悬浮待办

Windows 桌面悬浮便签式待办工具。Python + PySide6 + SQLite。

## 功能
- 桌面悬浮面板，始终置顶，可拖动
- 一键新增 / 完成待办
- 自动记录完成时间
- 已完成历史记录窗口
- 系统托盘常驻，关闭面板不退出
- 数据本地 SQLite 持久化
- **日历视图（网页版）**：跨所有便签的统一月历规划器（托盘 / 便签 ⋯ 菜单进入）
  - 点击后应用内起本地服务（仅 127.0.0.1，随机端口），用默认浏览器打开标准月历
  - 左侧栏：便签筛选 + 标签筛选（可叠加）+ 未安排日期的待办；拖到日期格即排期，拖回侧栏即取消日期
  - 日历网格：月 / 双周 / 周三视图，跨月导航、今天高亮、周末标色；日格内条目标题两行可读，超出可在格内滚动并显示条目数徽标；已完成灰显可反选恢复
  - 归档 Markdown 里的历史已办也按完成日铺进日历（只读灰显，点击看详情）
  - 点日格 ＋ 或双击空白新增：支持内容、标签、所属便签、日期、备注完整字段；点待办进编辑弹窗
  - 网页里的改动实时写回 SQLite 并同步刷新桌面悬浮便签
- **分析页（📊 标签页）**：与日历同一网页内切换（历史窗「分析」按钮直达）
  - 数据 = 归档 Markdown + 数据库里已完成未归档，自动合并（未归档条目带「未归档」徽标）
  - 数字卡 / 便签·标签联动筛选（选中便签后标签自动收窄）+ 时间区间筛选（预设/自定义）/ 完成热力图 / 按天清单
- **专注计时器**：在任意待办点 ⏱ 绑定计时
  - 倒计时（番茄钟，25/45/60/自定义，结束系统通知）+ 正向秒表两种模式
  - 累计专注时长写回该待办，行内显示 `⏱ Nm` 徽标

## 安装与运行
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Windows 一键启动 / 开机自启

### 双击启动（不用敲命令行）
项目根目录已带 `start.bat`，双击即可启动。`%~dp0` 会自动 `cd` 到脚本所在目录，
用 `pythonw.exe` 启动，无控制台黑窗口残留。

> 前提：`pythonw` 在 PATH 里。若装了 conda / venv，需要把对应 Scripts 目录加入 PATH，
> 或把 `start.bat` 里的 `pythonw` 改成绝对路径，例如 `.venv\Scripts\pythonw.exe`。

### 开机自启
1. 右键 `start.bat` → **创建快捷方式**。
2. `Win + R` → 输入 `shell:startup` 回车，把快捷方式拖进去。
3. 重启后托盘自动出现黄色圆点 = 成功。

不想自启时，把 Startup 文件夹里那个快捷方式删了即可，干干净净。

### 一键呼出
- **左键单击托盘图标**：把所有便签拉到最前并激活；如果已经全部在前面，则隐藏。
- **全局快捷键 `Ctrl + Alt + M`**：同上，不管当前在哪个窗口都能呼出。
  - 注册失败（按键冲突 / 杀软拦截）只会打印警告，不影响主程序。
  - 想换组合键：改 `main.py` 里 `GlobalHotkey("<ctrl>+<alt>+m")` 那行，
    格式参考 [pynput 文档](https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys)。

## 数据存储位置
- Windows: `%APPDATA%\DesktopTodo\todos.db`
- macOS / Linux: `~/.desktop_todo/todos.db`

## 数据隐私

真实数据库、归档记录和本地开发日志均已通过 `.gitignore` 排除，不应提交到仓库。
本仓库不附带任何真实数据或示例数据。

## 打包成 exe（Windows）
```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed ^
  --name DesktopTodo ^
  --add-data "app/webcal;app/webcal" ^
  main.py
```
产物：`dist\DesktopTodo.exe`

## 后续可扩展
- 每条待办独立便签窗口
- 优先级 / 标签 / 截止日期 / 提醒
- 数据导入导出
- 多主题 / 透明度调节
- 窗口位置记忆
