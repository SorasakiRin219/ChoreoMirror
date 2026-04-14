"""
模型配置模块

包含 MediaPipe 模型路径、下载 URL 和模型验证函数。
"""
import os
import sys
import urllib.request

# ══════════════════════════════════════════════════════════════
#  MediaPipe 模型配置
# ══════════════════════════════════════════════════════════════
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pose_landmarker_lite.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def ensure_model() -> None:
    """
    确保模型文件存在，不存在则自动下载。

    Raises:
        SystemExit: 如果模型下载失败
    """
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100_000:
        return

    print("[INFO] Downloading pose model (~3 MB)...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[OK]   Model ready.")
    except Exception as e:
        print("[ERROR]", e)
        sys.exit(1)
