"""
MJPEG 流处理模块

包含生成 MJPEG 视频流的函数。
"""
import time
import cv2
from flask import Response
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from processing.side_state import SideState


def gen_mjpeg_stream(side: "SideState", _lock) -> Generator[bytes, None, None]:
    """
    生成 MJPEG 视频流。

    Args:
        side: 单侧状态对象
        _lock: 全局状态锁

    Yields:
        MJPEG 帧数据
    """
    while True:
        with _lock:
            frame = side.latest_frame.copy()
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        time.sleep(1 / 30)
