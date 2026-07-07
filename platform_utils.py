import sys

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def is_windows():
    return IS_WINDOWS


def is_macos():
    return IS_MACOS


def is_linux():
    return IS_LINUX


def current_platform():
    if IS_WINDOWS:
        return "windows"
    if IS_MACOS:
        return "macos"
    if IS_LINUX:
        return "linux"
    return sys.platform
