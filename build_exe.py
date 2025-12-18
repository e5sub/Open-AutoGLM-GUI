#!/usr/bin/env python3
"""
打包脚本 - 将 gui.py 打包成 exe
"""

import os
import subprocess
import sys

def create_spec_file():
    """创建 PyInstaller spec 文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('adb.exe', '.'),
        ('AdbWinApi.dll', '.'),
        ('AdbWinUsbApi.dll', '.'),
        ('libwinpthread-1.dll', '.'),
        ('ADBKeyboard.apk', '.'),
        ('phone_agent', 'phone_agent'),
        ('main.py', '.'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'PIL',
        'PIL.Image',
        'openai',
        'phone_agent',
        'phone_agent.agent',
        'phone_agent.device_factory',
        'phone_agent.model',
        'phone_agent.model.client',
        'phone_agent.adb',
        'phone_agent.adb.connection',
        'phone_agent.adb.device',
        'phone_agent.adb.input',
        'phone_agent.adb.screenshot',
        'phone_agent.hdc',
        'phone_agent.hdc.connection',
        'phone_agent.hdc.device',
        'phone_agent.hdc.input',
        'phone_agent.hdc.screenshot',
        'phone_agent.actions',
        'phone_agent.actions.handler',
        'phone_agent.config',
        'phone_agent.config.apps',
        'phone_agent.config.apps_harmonyos',
        'phone_agent.config.i18n',
        'phone_agent.config.prompts',
        'phone_agent.config.prompts_zh',
        'phone_agent.config.prompts_en',
        'phone_agent.config.timing',
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
    icon=None,
)
'''
    
    with open('PhoneAgentGUI.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✓ PhoneAgentGUI.spec 文件已创建")

def build_exe():
    """执行打包命令"""
    print("📦 开始打包 gui.py...")
    
    # 清理之前的构建
    import shutil
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    # 使用 Python 模块方式调用 PyInstaller
    cmd = [
        'python', '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'PhoneAgentGUI',
        '--add-data', 'adb.exe;.',
        '--add-data', 'AdbWinApi.dll;.',
        '--add-data', 'AdbWinUsbApi.dll;.',
        '--add-data', 'libwinpthread-1.dll;.',
        '--add-data', 'ADBKeyboard.apk;.',
        '--add-data', 'phone_agent;phone_agent',
        '--add-data', 'main.py;.',
        '--hidden-import', 'tkinter',
        '--hidden-import', 'tkinter.ttk',
        '--hidden-import', 'tkinter.scrolledtext',
        '--hidden-import', 'tkinter.messagebox',
        '--hidden-import', 'tkinter.filedialog',
        '--hidden-import', 'PIL',
        '--hidden-import', 'PIL.Image',
        '--hidden-import', 'openai',
        '--hidden-import', 'phone_agent',
        '--hidden-import', 'phone_agent.agent',
        '--hidden-import', 'phone_agent.device_factory',
        '--hidden-import', 'phone_agent.model',
        '--hidden-import', 'phone_agent.model.client',
        '--hidden-import', 'phone_agent.adb',
        '--hidden-import', 'phone_agent.adb.connection',
        '--hidden-import', 'phone_agent.adb.device',
        '--hidden-import', 'phone_agent.adb.input',
        '--hidden-import', 'phone_agent.adb.screenshot',
        '--hidden-import', 'phone_agent.hdc',
        '--hidden-import', 'phone_agent.hdc.connection',
        '--hidden-import', 'phone_agent.hdc.device',
        '--hidden-import', 'phone_agent.hdc.input',
        '--hidden-import', 'phone_agent.hdc.screenshot',
        '--hidden-import', 'phone_agent.actions',
        '--hidden-import', 'phone_agent.actions.handler',
        '--hidden-import', 'phone_agent.config',
        '--hidden-import', 'phone_agent.config.apps',
        '--hidden-import', 'phone_agent.config.apps_harmonyos',
        '--hidden-import', 'phone_agent.config.i18n',
        '--hidden-import', 'phone_agent.config.prompts',
        '--hidden-import', 'phone_agent.config.prompts_zh',
        '--hidden-import', 'phone_agent.config.prompts_en',
        '--hidden-import', 'phone_agent.config.timing',
        'gui.py'
    ]
    
    print("📦 正在打包所有依赖...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("\n✅ 打包成功！")
            exe_path = os.path.join('dist', 'PhoneAgentGUI.exe')
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
                print(f"📁 exe 文件位置: {exe_path}")
                print(f"📊 文件大小: {file_size:.1f} MB")
                print("\n🎉 可以将 PhoneAgentGUI.exe 复制到其他电脑运行！")
                print("\n📝 注意事项：")
                print("1. 确保 ADB 工具和相关文件已正确打包")
                print("2. 运行时可能需要管理员权限")
                print("3. 首次运行可能需要配置 API Key")
            else:
                print("❌ exe 文件未找到")
            
            if result.stdout:
                print("\n📋 打包输出:")
                print(result.stdout[-1000:])  # 只显示最后1000字符
        else:
            print("\n❌ 打包失败！")
            if result.stderr:
                print("错误信息:")
                print(result.stderr)
            
    except Exception as e:
        print(f"\n❌ 打包过程中出现错误: {e}")

if __name__ == "__main__":
    build_exe()