# 桌面悬浮待办 Desktop Todo

<p align="center">
  <strong>把待办贴在桌面上，让记录、专注、规划和复盘连成一条线。</strong>
</p>

<p align="center">
  Windows 桌面悬浮便签式任务管理工具 · 本地优先 · Python + PySide6 + SQLite
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="PySide6" src="https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/Data-SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white">
</p>

<p align="center">
  <img src="docs/github-screenshots/01-floating-notes.png" width="430" alt="三张悬浮便签按工作、学习和生活分区显示">
</p>

## 产品定位

很多待办工具只有打开应用时才能看见，任务一多就重新藏回窗口、聊天记录和脑子里。

Desktop Todo 把多个清单做成可拖动、可置顶的桌面便签：随手记下任务后，可以直接开始专注计时；需要统筹时进入网页日历排期；完成后在分析页查看投入与进度。所有核心数据保存在本地，不依赖云端账号。

## 核心体验

| 能力 | 说明 |
| --- | --- |
| 多便签常驻桌面 | 为工作、学习、生活等场景建立独立便签，自由拖动并保持置顶 |
| 快速记录与整理 | 新增、编辑、完成、恢复待办；支持标签、日期、备注和 Markdown 存档 |
| 独立颜色主题 | 每张便签可选择不同主题色，降低多清单并行时的识别成本 |
| 任务专注计时 | 在任意待办旁启动 25/45/60 分钟倒计时、自定义倒计时或正向秒表 |
| 网页日历排期 | 通过本地网页按月、双周或周查看任务，拖拽即可安排或取消日期 |
| 完成数据复盘 | 汇总完成数量、专注时长、连续记录、热力图和按天完成清单 |
| 一键呼出 | 托盘单击或全局快捷键 `Ctrl + Alt + M` 显示/隐藏全部便签 |
| 本地数据优先 | SQLite、归档记录与网页服务均位于本机，网页服务只监听 `127.0.0.1` |

## 界面预览

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/01-floating-notes.png" alt="多便签分区"><br>
      <strong>多便签分区</strong><br>
      工作、学习、生活清单同时常驻桌面
    </td>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/02-color-themes.png" alt="颜色主题"><br>
      <strong>颜色主题</strong><br>
      用视觉优先级区分不同清单
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/03-focus-timer.png" alt="专注计时"><br>
      <strong>专注计时</strong><br>
      从“记下来”直接进入“开始做”
    </td>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/04-edit-and-export.png" alt="编辑与导出"><br>
      <strong>编辑与存档</strong><br>
      补充备注并将完成记录存档为 Markdown
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/05-weekly-calendar.png" alt="网页周日历"><br>
      <strong>网页日历</strong><br>
      跨便签排期，按周查看整体节奏
    </td>
    <td width="50%" align="center">
      <img src="docs/github-screenshots/06-progress-analytics.png" alt="完成数据分析"><br>
      <strong>完成复盘</strong><br>
      用热力图、专注时长和完成清单看见积累
    </td>
  </tr>
</table>

## 典型工作流

1. **捕捉**：在对应便签中快速记录任务，补充标签、日期或备注。
2. **行动**：点击任务旁的计时按钮，启动番茄钟或正向计时。
3. **规划**：打开网页日历，把不同便签中的任务拖到合适日期。
4. **完成**：勾选任务，完成时间与累计专注时长自动记录。
5. **复盘**：在分析页按便签、标签和时间范围查看进度与投入。

## 安装与运行

### 环境要求

- Windows 10 / 11
- Python 3.10+

### 从源码启动

```powershell
git clone https://github.com/JasmineZhangHM/desktop-todo.git
cd desktop-todo

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 双击启动

项目根目录提供 `start.bat`。完成依赖安装后，双击即可使用 `pythonw.exe` 静默启动，不保留控制台窗口。

如果使用虚拟环境，可将 `start.bat` 中的 `pythonw` 改为：

```bat
.venv\Scripts\pythonw.exe
```

## 使用说明

### 呼出与隐藏

- 左键单击托盘图标：显示全部便签；再次操作可隐藏。
- 按下 `Ctrl + Alt + M`：无论当前位于哪个窗口，都可以快速呼出便签。
- 关闭便签窗口不会退出应用；需要退出时请使用托盘菜单。

### 网页日历

- 从托盘菜单或便签的更多菜单打开。
- 本地服务只监听 `127.0.0.1`，并在默认浏览器中打开。
- 支持便签/标签组合筛选、月/双周/周视图、跨月导航和拖拽排期。
- 网页中的编辑会写回 SQLite，并同步刷新桌面便签。

### 分析页

- 与日历位于同一网页，通过顶部标签切换。
- 自动合并 Markdown 归档和数据库中尚未归档的完成记录。
- 支持时间范围、便签与标签联动筛选，并展示热力图、完成数和专注时长。

## 数据与隐私

核心数据默认只保存在本机：

- Windows：`%APPDATA%\DesktopTodo\todos.db`
- macOS / Linux：`~/.desktop_todo/todos.db`

真实数据库、归档记录、运行日志和本地开发文件均被 `.gitignore` 排除。本仓库不附带真实用户数据；界面截图使用虚构演示内容，并已遮挡浏览器收藏栏。

## 打包为 Windows EXE

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed ^
  --name DesktopTodo ^
  --add-data "app/webcal;app/webcal" ^
  main.py
```

生成文件位于 `dist\DesktopTodo.exe`。

## 项目结构

```text
desktop-todo/
├── app/
│   ├── floating_window.py   # 桌面悬浮便签
│   ├── timer_window.py      # 专注计时器
│   ├── history_window.py    # 已完成记录与 Markdown 存档
│   ├── web_calendar.py      # 本地网页服务
│   └── webcal/              # 日历与分析页前端
├── docs/                    # 产品截图
├── main.py                  # 应用入口
├── requirements.txt
└── start.bat
```

## Roadmap

- 截止日期提醒与系统通知增强
- 数据导入与备份恢复
- 更细粒度的窗口透明度和外观设置
- 可直接下载的 Windows 安装包

如果这个项目对你有帮助，欢迎提交 Issue、改进建议或使用反馈。
