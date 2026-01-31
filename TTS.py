import os
import time
import ctypes
from ctypes import c_int, c_void_p, c_bool, c_char_p, WINFUNCTYPE

# ===================== 核心配置 =====================
AISOUND_DLL_PATH = os.path.abspath("aisound.dll")
wrapperDLL = None
callback_func = None

# ===================== 类型定义 =====================
aisound_callback_t = WINFUNCTYPE(None, c_int, c_void_p)
SPEECH_BEGIN = 0
SPEECH_END = 1

# ===================== 回调函数 =====================
@aisound_callback_t
def aisound_callback_handler(type_, cbData):
    if type_ == SPEECH_BEGIN:
        print(f"📢 开始合成语音 | 索引: {cbData}")
    elif type_ == SPEECH_END:
        print(f"📢 语音合成完成 | 索引: {cbData}")

def Initialize():
    """初始化DLL"""
    global wrapperDLL, callback_func
    
    if not os.path.exists(AISOUND_DLL_PATH):
        raise FileNotFoundError(f"找不到DLL: {AISOUND_DLL_PATH}")
    
    wrapperDLL = ctypes.CDLL(AISOUND_DLL_PATH)
    print(f"✅ 成功加载DLL: {AISOUND_DLL_PATH}")
    
    # 定义函数原型
    wrapperDLL.aisound_initialize.restype = c_bool
    wrapperDLL.aisound_callback.restype = c_bool
    wrapperDLL.aisound_callback.argtypes = [aisound_callback_t]
    wrapperDLL.aisound_configure.restype = c_bool
    wrapperDLL.aisound_configure.argtypes = [c_char_p, c_char_p]
    wrapperDLL.aisound_speak.restype = c_bool
    wrapperDLL.aisound_speak.argtypes = [c_char_p, c_void_p]
    wrapperDLL.aisound_terminate.restype = c_bool
    
    # 初始化
    if not wrapperDLL.aisound_initialize():
        raise RuntimeError("❌ DLL初始化失败")
    
    # 注册回调
    callback_func = aisound_callback_handler
    if not wrapperDLL.aisound_callback(callback_func):
        raise RuntimeError("❌ 注册回调失败")
    
    print("✅ DLL初始化完成")

def Configure(name, value):
    """
    :param name: 配置项名称（字符串）
    :param value: 配置值（字符串/数字）
    :return: 是否配置成功
    """
    global wrapperDLL
    if not wrapperDLL:
        raise RuntimeError("请先调用Initialize()初始化")
    
    # 统一转UTF-8字节串
    name_bytes = name.encode("utf-8")
    value_bytes = str(value).encode("utf-8")
    
    res = wrapperDLL.aisound_configure(name_bytes, value_bytes)
    if res:
        print(f"✅ 配置成功 | {name} = {value}")
    else:
        print(f"❌ 配置失败 | {name} = {value}（DLL不识别该参数）")
    return res

def Speak(text, index=None):
    """Speak函数"""
    global wrapperDLL
    if not wrapperDLL:
        raise RuntimeError("请先调用Initialize()初始化")
    
    cbData = c_void_p(0 if index is None else index)
    text_bytes = text.encode("utf-8")
    
    res = wrapperDLL.aisound_speak(text_bytes, cbData)
    if res:
        print(f"✅ 发送合成指令: {text}")
    else:
        raise RuntimeError(f"❌ 合成失败: {text}")
    return res

def Terminate():
    """Terminate函数"""
    global wrapperDLL
    if wrapperDLL:
        wrapperDLL.aisound_terminate()
        print("✅ DLL已终止")

# 测试
if __name__ == "__main__":
    try:
        Initialize()
        
        Configure("volume", 32767)
        Configure("speed", 32767)
        Configure("pitch", 0)
        Configure("voice", "babyXu")
        Configure("inflection", 1.11)
        
        Speak("你好，按原文档方式配置的参数已生效")
        
        # 等待播放完成
        time.sleep(5)
        
    except Exception as e:
        print(f"❌ 出错: {e}")
    finally:
        Terminate()
        print("👋 程序结束")
