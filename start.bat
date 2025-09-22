@echo off
title 240fps录制程序
cls

echo =====================================
echo      240fps 录制程序启动器
echo =====================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在！
    echo 请确保在项目根目录下存在 venv 文件夹
    echo.
    pause
    exit /b 1
)

REM 激活虚拟环境
echo [信息] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 检查必要的依赖是否已安装
echo [信息] 检查依赖包...
py -c "import cv2, PIL" >nul 2>&1
if errorlevel 1 (
    echo [警告] 依赖包缺失，正在安装...
    py -m pip install opencv-python Pillow
    echo [信息] 依赖包安装完成
)

echo [信息] 启动主程序...
echo =====================================
echo.

REM 运行主程序
py sync_measure_and_record.py

echo.
echo =====================================
echo [信息] 程序已退出
echo 按任意键关闭窗口...
pause >nul
