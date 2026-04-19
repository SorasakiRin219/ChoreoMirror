"""
镜影鉴姿Choreomirror-舞蹈动作分析系统 v3.1

主包初始化文件，导出主要类和函数
"""

# 版本信息
__version__ = "3.1.0"
__author__ = "SorasakiRin"

# 导出主要类（延迟导入，避免循环依赖）
def get_app_state():
    """获取全局应用状态实例"""
    from processing.app_state import AppState
    return AppState()
