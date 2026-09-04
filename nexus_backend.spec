# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for NEXUS backend bundling
# Builds a single-file Windows exe: nexus_backend.exe

import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all data/binaries from google-genai and uvicorn
datas = [
    # Bundle the NEXUS config TOML
    ('config/default.toml', 'config'),
    # Bundle all nexus source code as a package
    ('src/nexus', 'nexus'),
]

binaries = []
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.off',
    'fastapi',
    'starlette',
    'starlette.routing',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'aiosqlite',
    'aiofiles',
    'google.genai',
    'google.generativeai',
    'pydantic',
    'pydantic_settings',
    'dotenv',
    'PIL',
    'PIL.Image',
    'nexus.main',
    'nexus.api.app',
    'nexus.api.routes',
    'nexus.core.config',
    'nexus.database.engine',
]

# Collect all submodules from nexus packages
for pkg in ['nexus', 'uvicorn', 'fastapi', 'starlette']:
    hiddenimports += collect_submodules(pkg)

# Collect google-genai data
genai_datas, genai_binaries, genai_imports = collect_all('google.genai')
datas += genai_datas
binaries += genai_binaries
hiddenimports += genai_imports

# Key dependencies hidden imports
hiddenimports += [
    'numpy',
    'sounddevice',
    'speech_recognition',
    'edge_tts',
    'pyttsx3',
    'psutil',
    'pyautogui',
    'mouseinfo',
    'pygetwindow',
    'pyrect',
    'pyscreeze',
    'pyperclip',
]

a = Analysis(
    ['src/nexus/main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    excludes=['tkinter', 'matplotlib', 'pandas', 'scipy'],
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
    name='nexus_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No console window shown to end user
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='build/icon.png',
)
