block_cipher = None


a = Analysis(
    ['MapEditor.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['wx.adv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['ctypes.wintypes', 'winreg'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MapEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.datas,
    name='MapEditor.app',
    icon=None,
    bundle_identifier='com.mapeditor.app',
    info_plist={
        'CFBundleName': 'MapEditor',
        'CFBundleDisplayName': '地图编辑器',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
    },
)
