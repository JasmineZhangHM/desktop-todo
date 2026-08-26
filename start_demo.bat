@echo off
cd /d "%~dp0"

rem 演示模式使用项目内的独立 APPDATA，不读取真实用户数据库。
set "APPDATA=%~dp0DemoData"

rem 首次启动或演示数据版本升级时，生成通用职场项目场景的演示数据库。
python DemoData\seed_workplace_demo.py
if errorlevel 1 (
    echo 演示数据库生成失败，请检查 Python 和依赖环境。
    pause
    exit /b 1
)

rem 必须使用上面这个 python 同一环境里的 pythonw，避免系统 PATH 中的
rem pythonw 指向另一套未安装 PySide6 的 Python。
set "DEMO_PYTHONW="
for /f "usebackq delims=" %%P in (`python -c "import pathlib,sys; p=pathlib.Path(sys.executable).with_name('pythonw.exe'); print(p if p.exists() else '')"`) do set "DEMO_PYTHONW=%%P"

if not defined DEMO_PYTHONW (
    echo 找不到与当前 Python 配套的 pythonw.exe。
    echo 请在此窗口运行 python main.py，或检查 Python 安装。
    pause
    exit /b 1
)

start "" "%DEMO_PYTHONW%" main.py
