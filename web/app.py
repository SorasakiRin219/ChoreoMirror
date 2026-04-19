"""
Flask 应用初始化模块，
创建和配置 Flask 应用实例
"""
import os
from flask import Flask

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 全局状态实例（延迟导入以避免循环依赖）
_STATE = None


def get_state():
    """获取全局应用状态实例"""
    global _STATE
    if _STATE is None:
        from processing.app_state import AppState
        _STATE = AppState()
    return _STATE


def create_app() -> Flask:
    """
    创建并配置 Flask 应用

    Returns:
        配置好的 Flask 应用实例
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(_HERE, 'templates'),
        static_folder=os.path.join(_HERE, 'static')
    )
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB

    # 注册路由
    from .routes import register_routes
    register_routes(app)

    return app


# 导出全局状态供其他模块使用
def state():
    """获取全局状态实例的快捷函数"""
    return get_state()
