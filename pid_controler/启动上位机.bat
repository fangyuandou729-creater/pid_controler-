@echo off
chcp 65001 >nul 2>nul
title 模仿者小队 - 直流减速电机闭环控制上位机
cd /d "%~dp0"
echo ============================================
echo   模仿者小队 - DC Motor PID Controller
echo   直流减速电机闭环控制上位机
echo ============================================
echo.
echo 正在启动...
echo.

:: 尝试 py 启动器
py -3 main.py 2>nul
if %errorlevel% equ 0 goto :end

:: 尝试 python3
python3 main.py 2>nul
if %errorlevel% equ 0 goto :end

:: 尝试 python
python main.py 2>nul
if %errorlevel% equ 0 goto :end

:: 尝试完整路径
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" main.py 2>nul
if %errorlevel% equ 0 goto :end

:: 全部失败
echo.
echo ==========================================
echo  错误: 未找到Python环境!
echo  请安装Python 3.8+ 并确保已添加到PATH
echo  下载地址: https://www.python.org/downloads/
echo ==========================================
echo.
pause

:end