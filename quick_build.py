#!/usr/bin/env python3
"""
快速打包脚本 - 只打包GUI和必要文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def quick_build():
    """快速构建GUI程序"""
    print("=== PhoneAgent GUI 快速打包 ===")
    print()
    
    # 检查文件
    required_files = ['gui.py', 'ADBKeyboard.apk', 'adb.exe']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ 缺少必要文件: {file}")
            return False
    
    print("✅ 必要文件检查通过")
    
    # 安装 PyInstaller
    print("正在安装 PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True, capture_output=True)
        print("✅ PyInstaller 安装成功")
    except subprocess.CalledProcessError:
        print("❌ PyInstaller 安装失败，请检查网络连接")
        return False
    
    # 清理之前的构建
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=PhoneAgentGUI',
        '--onefile',  # 单文件模式
        '--windowed',  # 无控制台窗口
        '--clean',
        '--noconfirm',
        '--add-data=ADBKeyboard.apk;.',
        '--add-data=adb.exe;.',
        '--add-data=AdbWinApi.dll;.',
        '--add-data=AdbWinUsbApi.dll;.',
        '--add-data=libwinpthread-1.dll;.',
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.scrolledtext',
        '--hidden-import=tkinter.messagebox',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=PIL._tkinter_finder',
        'gui.py'
    ]
    
    print("正在构建可执行文件...")
    print("这可能需要几分钟，请耐心等待...")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 构建成功!")
        
        # 检查输出文件
        exe_path = Path('dist/PhoneAgentGUI.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 可执行文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")
            return True
        else:
            print("❌ 未找到可执行文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        if e.stderr:
            print(f"错误信息: {e.stderr}")
        return False

def create_simple_portable():
    """创建简单的便携版"""
    print("正在创建便携版...")
    
    dist_dir = Path('dist')
    portable_dir = dist_dir / 'Portable'
    
    portable_dir.mkdir(exist_ok=True)
    
    # 复制可执行文件
    exe_src = dist_dir / 'PhoneAgentGUI.exe'
    exe_dst = portable_dir / 'PhoneAgentGUI.exe'
    if exe_src.exists():
        shutil.copy2(exe_src, exe_dst)
        print("✅ 复制可执行文件成功")
    
    # 复制ADB相关文件
    adb_files = ['adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'libwinpthread-1.dll', 'ADBKeyboard.apk']
    for file in adb_files:
        if os.path.exists(file):
            shutil.copy2(file, portable_dir / file)
    
    # 创建简单的说明
    readme = '''PhoneAgent GUI 便携版

使用方法:
1. 双击 PhoneAgentGUI.exe 启动程序
2. 如果ADB连接失败，请确保手机已开启USB调试

注意事项:
- 首次启动可能较慢
- 无需安装Python环境
- 支持Windows 7/8/10/11 64位
'''
    
    with open(portable_dir / '使用说明.txt', 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"✅ 便携版创建完成: {portable_dir}")

def main():
    if quick_build():
        create_simple_portable()
        print()
        print("🎉 打包完成!")
        print()
        print("输出文件:")
        print("  - 单文件: dist/PhoneAgentGUI.exe")
        print("  - 便携版: dist/Portable/")
        print()
        print("可以直接运行 PhoneAgentGUI.exe 测试")
    else:
        print()
        print("❌ 打包失败，请检查错误信息")

if __name__ == "__main__":
    main()