# -*- mode: python -*-
import os
import site
from pathlib import Path

block_cipher = None

a = Analysis(
    [Path.cwd() / "__main__.py"],
    pathex=["."],
    binaries=[
        ("rhasspyasr_pocketsphinx/estimate-ngram", "."),
        ("rhasspyasr_pocketsphinx/libfst.so.13", "."),
        ("rhasspyasr_pocketsphinx/libfstfar.so.13", "."),
        ("rhasspyasr_pocketsphinx/libfstngram.so.13", "."),
        ("rhasspyasr_pocketsphinx/libmitlm.so.1", "."),
        ("rhasspyasr_pocketsphinx/phonetisaurus-g2pfst", "."),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
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
    [],
    exclude_binaries=True,
    name="rhasspyasr_pocketsphinx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="rhasspyasr_pocketsphinx",
)
