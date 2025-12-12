@echo off
chcp 65001 >nul
title PhoneAgent GUI 打包工具
echo.
echo ========================================
echo    PhoneAgent GUI 打包工具
echo ========================================
echo.

echo 正在检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python 环境检查通过
echo.

echo 开始打包，这可能需要几分钟时间...
echo.

python build_exe.py

echo.
echo 打包完成！
echo 可执行文件位置: dist\PhoneAgentGUI.exe
echo 便携版目录: dist\PhoneAgent_Portable\
echo.
pause