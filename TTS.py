import sys
import os
import time
import ctypes
from ctypes import c_int, c_bool, c_void_p, c_char_p, CFUNCTYPE

# ================= 配置部分 =================
DLL_NAME = "aisound.dll"
dll_path = os.path.abspath(DLL_NAME)

if not os.path.exists(dll_path):
    print(f"错误: 找不到 {DLL_NAME}，请确保它在当前脚本同级目录下。")
    sys.exit(1)

# ================= 加载 DLL =================
try:
    # 自动识别加载方式，Windows下通常是CDLL
    aisound = ctypes.CDLL(dll_path)
except OSError as e:
    print(f"DLL加载失败: {e}")
    print("请检查：1. Python版本(32/64位)是否与DLL匹配；2. 是否缺少依赖库(如VC++运行库)。")
    sys.exit(1)

# ================= 定义类型与常量 =================
# 回调函数类型：void callback(int cmd, void* data)
# 必须定义为 CFUNCTYPE 以防止被 Python 垃圾回收
CALLBACK_TYPE = CFUNCTYPE(None, c_int, c_void_p)

SPEECH_BEGIN = 0
SPEECH_END = 1

# ================= 设置函数签名 (ArgTypes) =================
# 这是一个好习惯，能防止参数传递错误导致的崩溃
aisound.aisound_initialize.restype = c_bool
aisound.aisound_initialize.argtypes = []  # 原代码中此处无参或被忽略

aisound.aisound_terminate.restype = c_bool
aisound.aisound_terminate.argtypes = []

aisound.aisound_configure.restype = c_bool
aisound.aisound_configure.argtypes = [c_char_p, c_char_p] # 键, 值

aisound.aisound_speak.restype = c_bool
# 注意：第二个参数是 void*，用于传递索引ID，我们这里简单传入整数即可
aisound.aisound_speak.argtypes = [c_char_p, c_void_p]

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

# ================= 主流程 =================
def main():
    print("--- 初始化引擎 ---")
    if not aisound.aisound_initialize():
        print("初始化失败！")
        return

    print("--- 注册回调 ---")
    # 注册我们定义的回调函数
    aisound.aisound_callback(global_callback_ref)

    print("--- 配置参数 ---")
    # 参考 NVDA 代码，配置需转为 utf-8
    # 常用配置：voice, rate(speed), volume, pitch
    # 注意：某些版本的 aisound 可能需要 gbk，如果乱码请改为 gbk
    cfg_encoding = "utf-8" 
    
    params = {
        "voice": "YanPing",  # 或 BabyXu
        "volume": "100",     # 0-100 或 DLL特定范围
        "speed": "50"        # 0-100
    }

    for k, v in params.items():
        aisound.aisound_configure(k.encode(cfg_encoding), v.encode(cfg_encoding))

    print("--- 开始朗读 ---")
    text = "你好，这是一段去除了所有复杂逻辑的纯净测试代码。"
    
    # 这里的 1001 是自定义的 ID，会在回调里传回来
    # text.encode 同样要注意可能是 gbk
    success = aisound.aisound_speak(text.encode(cfg_encoding), c_void_p(1001))
    
    if success:
        print("指令发送成功，正在播放...")
        # 【关键】：因为 DLL 是异步播放的，主线程不能死，否则声音会立刻中断
        # 我们使用死循环等待，直到大概读完，或者监听回调（简单起见这里用 sleep）
        time.sleep(5) 
    else:
        print("指令发送失败 (返回 False)")

    print("--- 释放资源 ---")
    aisound.aisound_terminate()

if __name__ == "__main__":
    main()