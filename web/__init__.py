"""
Web 模块

包含 Flask 应用、API 路由和 MJPEG 流处理。
"""

from .app import create_app
from .routes import register_routes
from .streaming import gen_mjpeg_stream

__all__ = [
    "create_app",
    "register_routes",
    "gen_mjpeg_stream",
]
