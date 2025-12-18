# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('adb.exe', '.'), ('AdbWinApi.dll', '.'), ('AdbWinUsbApi.dll', '.'), ('libwinpthread-1.dll', '.'), ('ADBKeyboard.apk', '.'), ('phone_agent', 'phone_agent'), ('main.py', '.')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.messagebox', 'tkinter.filedialog', 'PIL', 'PIL.Image', 'openai', 'phone_agent', 'phone_agent.agent', 'phone_agent.device_factory', 'phone_agent.model', 'phone_agent.model.client', 'phone_agent.adb', 'phone_agent.adb.connection', 'phone_agent.adb.device', 'phone_agent.adb.input', 'phone_agent.adb.screenshot', 'phone_agent.hdc', 'phone_agent.hdc.connection', 'phone_agent.hdc.device', 'phone_agent.hdc.input', 'phone_agent.hdc.screenshot', 'phone_agent.actions', 'phone_agent.actions.handler', 'phone_agent.config', 'phone_agent.config.apps', 'phone_agent.config.apps_harmonyos', 'phone_agent.config.i18n', 'phone_agent.config.prompts', 'phone_agent.config.prompts_zh', 'phone_agent.config.prompts_en', 'phone_agent.config.timing'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
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
)
