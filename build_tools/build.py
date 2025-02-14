import PyInstaller.__main__
import os

def build():
    PyInstaller.__main__.run([
        'run.py',
        '--onefile',
        '--windowed',
        '--icon=installer/app.ico',
        '--name=视频自动发布工具',
        '--add-data=src/config;src/config',
        '--noconsole',
    ])

if __name__ == "__main__":
    build() 