"""
工具模块，
包含辅助函数
"""
import webbrowser
import time

from config.model_config import ensure_model


def open_browser():
    """在浏览器中打开应用"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")
