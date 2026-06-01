import ctypes
import os
import sys
from ctypes import c_int, c_wchar_p


DLL_NAME = "nvdaControllerClient32.dll"

_dll = None
_initialized = False


def _app_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _dll_path():
    return os.path.join(_app_dir(), DLL_NAME)


def _load_dll():
    global _dll
    if _dll is not None:
        return _dll

    path = _dll_path()
    if not os.path.exists(path):
        print(f"错误: 找不到 {DLL_NAME}。")
        return None

    try:
        dll = ctypes.CDLL(path)
    except OSError as e:
        print(f"DLL加载失败: {e}")
        return None

    dll.nvdaController_testIfRunning.restype = c_int
    dll.nvdaController_testIfRunning.argtypes = []

    dll.nvdaController_speakText.restype = c_int
    dll.nvdaController_speakText.argtypes = [c_wchar_p]

    dll.nvdaController_cancelSpeech.restype = c_int
    dll.nvdaController_cancelSpeech.argtypes = []

    _dll = dll
    return _dll


def init_engine():
    global _initialized
    dll = _load_dll()
    if dll is None:
        _initialized = False
        return False

    try:
        running = dll.nvdaController_testIfRunning() == 0
    except OSError as e:
        print(f"NVDA Controller 调用失败: {e}")
        _initialized = False
        return False

    if not running:
        print("NVDA 未运行或 NVDA Controller 不可用。")
        _initialized = False
        return False

    _initialized = True
    return True


def speak(text, index=None):
    del index
    if text is None:
        return False

    dll = _load_dll()
    if dll is None:
        return False

    try:
        if not _initialized and dll.nvdaController_testIfRunning() != 0:
            print("NVDA 未运行或 NVDA Controller 不可用。")
            return False
        dll.nvdaController_cancelSpeech()
        return dll.nvdaController_speakText(str(text)) == 0
    except OSError as e:
        print(f"NVDA Controller 调用失败: {e}")
        return False


def cancel():
    dll = _load_dll()
    if dll is None:
        return False
    try:
        return dll.nvdaController_cancelSpeech() == 0
    except OSError as e:
        print(f"NVDA Controller 调用失败: {e}")
        return False


def terminate():
    cancel()


if __name__ == "__main__":
    pass
