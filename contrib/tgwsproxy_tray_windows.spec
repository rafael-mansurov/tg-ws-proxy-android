# PyInstaller: из корня репозитория
#   pip install pyinstaller -r contrib/requirements-tray-windows.txt
#   pyinstaller contrib/tgwsproxy_tray_windows.spec
# Результат: dist/TGWSProxyTray.exe (one-file, без консоли).

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# SPECPATH задаёт PyInstaller при загрузке .spec (каталог, где лежит файл).
SPECDIR = Path(SPECPATH)
ROOT = SPECDIR.parent

crypt_datas, crypt_binaries, crypt_hidden = collect_all("cryptography")

datas = [
    (str(ROOT / "scripts" / "run_local_proxy.py"), "scripts"),
    (str(ROOT / "scripts" / "qrcodegen_nayuki.py"), "scripts"),
]
datas += crypt_datas

binaries = crypt_binaries

hiddenimports = (
    list(crypt_hidden)
    + collect_submodules("proxy")
    + [
        "PIL.Image",
        "PIL.ImageDraw",
        "pystray",
        "pystray._win32",
        "qrcodegen_nayuki",
    ]
)

a = Analysis(
    [str(SPECDIR / "tgwsproxy_tray_windows.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy"],
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
    name="TGWSProxyTray",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
