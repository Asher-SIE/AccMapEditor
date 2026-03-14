@echo off
chcp 65001 >nul
title 打包 MapEditor

echo   MapEditor 打包脚本
echo ========================================
echo.

REM 激活虚拟环境

echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 检查是否激活成功
if errorlevel 1 (
    echo 虚拟环境激活失败！
    pause
    exit /b 1
)

echo 虚拟环境激活成功！
echo 清理旧的构建文件...
rd /s /q dist\
rd /s /q build\

REM 运行 PyInstaller 打包
echo 开始打包...
pyinstaller MapEditor.spec --clean

if errorlevel 1 (
    echo 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo ========================================

REM 退出虚拟环境
call venv\Scripts\deactivate.bat

pause