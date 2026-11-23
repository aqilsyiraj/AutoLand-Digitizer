# -*- mode: python ; coding: utf-8 -*-
"""
AutoLand Digitizer - PyInstaller Build Specification (Ultra-Lightweight)
Konfigurasi kompilasi yang dioptimasi untuk ukuran file minimal dan startup instan:
- Mengecualikan modul-modul raksasa PySide6 yang tidak digunakan (WebEngine, QML, Quick, 3D, dll)
- Mengecualikan pustaka eksternal yang tidak diperlukan (scipy, matplotlib, tkinter, dll)
- Menyaring binary/DLL bawaan yang tidak terpakai (ffmpeg videoio, software OpenGL Mesa, dll)
- Mengaktifkan level optimasi bytecode Python (optimize=1)
"""

excludes = [
    # Modul PySide6 yang tidak digunakan (menghemat > 150 MB)
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQuick3D',
    'PySide6.QtQml',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DExtras',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtBluetooth',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtLocation',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio',
    'PySide6.QtSql',
    'PySide6.QtTest',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtNetworkAuth',
    'PySide6.QtScxml',
    'PySide6.QtRemoteObjects',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',

    # Pustaka Python bawaan dan dependensi berat yang tidak dipakai
    'scipy',
    'matplotlib',
    'tkinter',
    'IPython',
    'tornado',
    'unittest',
    'test',
    'distutils',
    'setuptools',
    'pip',
    'wheel',
    'pytest',
    'pdf2docx',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('template', 'template')],
    hiddenimports=[
        'win32com.client',
        'pythoncom',
        'openpyxl',
        'pymupdf',
        'PIL',
        'numpy',
        'cv2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

# Saring DLL dan binary besar yang tidak diperlukan (menghemat > 60 MB tambahan)
unwanted_binaries = [
    'opencv_videoio_ffmpeg',
    'opengl32sw',
    'qt6quick',
    'qt6qml',
    'qt6pdf',
    'qt6virtualkeyboard',
]

a.binaries = [
    b for b in a.binaries
    if not any(pattern in b[0].lower() for pattern in unwanted_binaries)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoLandDigitizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoLandDigitizer',
)
