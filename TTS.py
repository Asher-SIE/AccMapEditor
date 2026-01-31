import sys
import os
import ctypes
from ctypes import c_int, c_bool, c_void_p, c_char_p, CFUNCTYPE

# ================= 配置部分 =================
DLL_NAME = "aisound.dll"
dll_path = os.path.abspath(DLL_NAME)

if not os.path.exists(dll_path):
    print(f"错误: 找不到 {DLL_NAME}。")
    sys.exit(1)

# ================= 加载 DLL =================
try:
    aisound = ctypes.CDLL(dll_path)
except OSError as e:
    print(f"DLL加载失败: {e}")
    sys.exit(1)

# ================= 定义类型与常量 =================
# 回调函数类型：void callback(int cmd, void* data)
# 必须定义为 CFUNCTYPE 以防止被 Python 垃圾回收
CALLBACK_TYPE = CFUNCTYPE(None, c_int, c_void_p)

SPEECH_BEGIN = 0
SPEECH_END = 1

# 设置函数签名 (ArgTypes)
aisound.aisound_initialize.restype = c_bool
aisound.aisound_initialize.argtypes = []

aisound.aisound_terminate.restype = c_bool
aisound.aisound_terminate.argtypes = []

aisound.aisound_configure.restype = c_bool
aisound.aisound_configure.argtypes = [c_char_p, c_char_p]

aisound.aisound_speak.restype = c_bool
aisound.aisound_speak.argtypes = [c_char_p, c_void_p]

aisound.aisound_cancel.restype=c_bool
aisound.aisound_pause.restype=c_bool
aisound.aisound_resume.restype=c_bool

aisound.aisound_callback.restype = c_bool
aisound.aisound_callback.argtypes = [CALLBACK_TYPE]

# ================= Python 回调实现 =================
def on_status_change(cmd, data):
    """
    DLL 通知状态的回调
    """
    if cmd == SPEECH_BEGIN:
        print(f"[回调] 开始朗读 (ID: {data})")
    elif cmd == SPEECH_END:
        print("[回调] 朗读结束")

#以此变量保持对回调函数的引用，防止被GC回收导致崩溃
global_callback_ref = CALLBACK_TYPE(on_status_change)


# 配置参数
cfg_encoding = "utf-8" 

params = {
    "voice": "YanPing",
    "volume": "32767",
    "speed": "32767"
}


# 初始化
def init_engine():
    print("--- 初始化引擎 ---")
    if not aisound.aisound_initialize():
        print("初始化失败！")
        return

    print("--- 注册回调 ---")
    aisound.aisound_callback(global_callback_ref)


    for k, v in params.items():
        aisound.aisound_configure(k.encode(cfg_encoding), v.encode(cfg_encoding))


def speak(text, index=None):
    print("--- 开始朗读 ---")
    
    success = aisound.aisound_speak(text.encode(cfg_encoding), index)
    
    if success:
        print("开始朗读")
        
    else:
        print("朗读失败")


def cancel():
    success = aisound.aisound_cancel()
    if success:
        print('朗读已停止')




def terminate():
    print("--- 释放资源 ---")
    aisound.aisound_terminate()


if __name__ == "__main__":
    pass