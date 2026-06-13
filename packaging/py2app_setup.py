"""
py2app 打包脚本 - Workflow Engine
==================================
使用方法:
    python packaging/py2app_setup.py py2app
"""

from setuptools import setup

APP = ["src/macos/app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "packages": ["src"],
    "includes": ["tkinter"],
    "excludes": ["matplotlib", "numpy", "scipy", "pandas", "vue"],
    "iconfile": None,
    "plist": {
        "CFBundleName": "Workflow Engine",
        "CFBundleDisplayName": "Workflow Engine",
        "CFBundleIdentifier": "com.dirjaker.workflow-engine",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHumanReadableCopyright": "MIT License",
    },
}

setup(
    name="Workflow Engine",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
