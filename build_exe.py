#!/usr/bin/env python3
"""
打包 Phone Agent GUI 为 Windows 可执行程序
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_pyinstaller():
    """安装 PyInstaller"""
    print("正在安装 PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✅ PyInstaller 安装成功")
    except subprocess.CalledProcessError:
        print("❌ PyInstaller 安装失败")
        return False
    return True

def create_spec_file():
    """创建 PyInstaller 规格文件"""
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ADBKeyboard.apk', '.'),
        ('adb.exe', '.'),
        ('AdbWinApi.dll', '.'),
        ('AdbWinUsbApi.dll', '.'),
        ('libwinpthread-1.dll', '.'),
        ('etc1tool.exe', '.'),
        ('fastboot.exe', '.'),
        ('hprof-conv.exe', '.'),
        ('mke2fs.conf', '.'),
        ('mke2fs.exe', '.'),
        ('make_f2fs.exe', '.'),
        ('make_f2fs_casefold.exe', '.'),
        ('sqlite3.exe', '.'),
        ('phone_agent', 'phone_agent'),
    ],
    hiddenimports=[
        'phone_agent',
        'phone_agent.agent',
        'phone_agent.utils',
        'phone_agent.adb_tools',
        'PIL._tkinter_finder',
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'subprocess',
        'threading',
        'json',
        'datetime',
        're',
        'os',
        'sys',
        'platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhoneAgentGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
'''
    
    with open('gui.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("✅ 创建 gui.spec 文件成功")

def create_version_info():
    """创建版本信息文件"""
    version_info = '''
# UTF-8
#
# 版本信息文件
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'PhoneAgent'),
            StringStruct(u'FileDescription', u'AI手机自动化工具'),
            StringStruct(u'FileVersion', u'1.0.0.0'),
            StringStruct(u'InternalName', u'PhoneAgentGUI'),
            StringStruct(u'LegalCopyright', u'Copyright (C) 2024'),
            StringStruct(u'OriginalFilename', u'PhoneAgentGUI.exe'),
            StringStruct(u'ProductName', u'PhoneAgent GUI'),
            StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    print("✅ 创建 version_info.txt 文件成功")

def build_exe():
    """构建可执行文件"""
    print("正在构建可执行文件...")
    
    # 清理之前的构建
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    try:
        # 运行 PyInstaller
        subprocess.run([
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            'gui.spec'
        ], check=True)
        print("✅ 可执行文件构建成功")
        return True
    except subprocess.CalledProcessError:
        print("❌ 可执行文件构建失败")
        return False

def create_portable_package():
    """创建便携版压缩包"""
    print("正在创建便携版...")
    
    dist_dir = Path('dist')
    portable_dir = dist_dir / 'PhoneAgent_Portable'
    
    # 创建便携版目录
    portable_dir.mkdir(exist_ok=True)
    
    # 复制可执行文件
    exe_path = dist_dir / 'PhoneAgentGUI.exe'
    if exe_path.exists():
        shutil.copy2(exe_path, portable_dir / 'PhoneAgentGUI.exe')
        print("✅ 复制可执行文件成功")
    
    # 创建说明文件
    readme_content = '''# PhoneAgent GUI 便携版

## 使用说明

1. 双击 `PhoneAgentGUI.exe` 启动程序
2. 首次启动可能需要几秒钟加载时间
3. 程序会自动创建配置文件 `gui_config.json`
4. 确保 Android 设备已启用 USB 调试模式

## 功能特性

- 🤖 AI驱动的手机自动化工具
- 📱 ADB设备管理和连接
- 🔗 支持远程ADB连接
- 📲 一键安装ADB键盘
- 💾 配置文件保存和加载

## 系统要求

- Windows 7/8/10/11 (64位)
- 已安装USB驱动（如果使用USB连接）

## 问题排查

如果遇到"缺少DLL"错误：
1. 安装 Microsoft Visual C++ Redistributable
2. 确保 Windows 系统更新到最新版本

如果ADB连接失败：
1. 确保设备已启用USB调试
2. 检查USB驱动是否正确安装
3. 尝试使用"远程连接"功能

## 更新日期

2024年12月
'''
    
    with open(portable_dir / 'README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    # 创建启动脚本
    bat_content = '''@echo off
echo 启动 PhoneAgent GUI...
echo.
start "" "PhoneAgentGUI.exe"
'''
    
    with open(portable_dir / '启动PhoneAgentGUI.bat', 'w', encoding='gbk') as f:
        f.write(bat_content)
    
    print("✅ 便携版创建成功")
    print(f"📦 便携版位置: {portable_dir}")

def main():
    """主函数"""
    print("=== PhoneAgent GUI 打包工具 ===")
    print()
    
    # 检查当前目录
    if not os.path.exists('gui.py'):
        print("❌ 错误: 请在项目根目录运行此脚本")
        return
    
    # 安装 PyInstaller
    if not install_pyinstaller():
        return
    
    # 创建规格文件
    create_spec_file()
    
    # 创建版本信息
    create_version_info()
    
    # 构建可执行文件
    if not build_exe():
        return
    
    # 创建便携版
    create_portable_package()
    
    print()
    print("🎉 打包完成!")
    print()
    print("📁 输出目录:")
    print("   - 可执行文件: dist/PhoneAgentGUI.exe")
    print("   - 便携版目录: dist/PhoneAgent_Portable/")
    print()
    print("📝 建议:")
    print("   1. 测试可执行文件是否能正常运行")
    print("   2. 可以将便携版目录压缩后分享给其他用户")
    print("   3. 可执行文件约 50-100MB，首次启动较慢是正常的")

if __name__ == "__main__":
    main()