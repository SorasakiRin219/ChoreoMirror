"""
镜影鉴姿-舞蹈动作分析系统 v3.1
启动入口
"""
import os
import socket
import sys
import threading
import warnings

warnings.filterwarnings("ignore")

# 模块导入
from config.model_config import ensure_model
from web.app import create_app
from utils.helpers import open_browser

# 可选依赖检测
missing = []
try:
    import anthropic
except ImportError:
    missing.append("anthropic")

try:
    import openai
except ImportError:
    missing.append("openai")

try:
    import ezc3d
except ImportError:
    missing.append("ezc3d")


def get_lan_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def main():
    """主函数"""
    lan_ip = get_lan_ip()

    print(f"""
+================================================+
|   镜影鉴姿-舞蹈动作分析系统 v3.1                 |
|   浏览器将在 2 秒后自动打开                     |
|                                                |
|   本机访问: http://127.0.0.1:5000              |
|   局域网访问: http://{lan_ip}:5000             |
|                                                |
|   按 Ctrl+C 停止                                 |
+================================================+""")

    if missing:
        print(f"[WARN] 可选功能缺失，可运行: pip install {' '.join(missing)}")

    # 确保模型文件存在
    ensure_model()

    # 在后台线程中打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 创建并启动 Flask 应用
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
