"""
全局应用状态模块

包含 AppState 类，用于管理全局应用状态。
"""
import os
import threading
from typing import Dict, Optional

from core.comparison import compare_sides
from .side_state import SideState
from .side_processor import SideProcessor


class AppState:
    """
    全局应用状态管理类。

    管理两侧（A/B）的状态、AI 设置、对比结果等全局信息。
    """

    def __init__(self):
        """初始化全局应用状态"""
        self._lock = threading.Lock()
        self.side_a = SideState("A")
        self.side_b = SideState("B")
        self.comparison: Optional[Dict] = None
        self.last_advice = ""

        # AI 服务商设置
        self.api_keys: Dict[str, str] = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
            "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
            "openai": os.environ.get("OPENAI_API_KEY", ""),
            "qwen": os.environ.get("DASHSCOPE_API_KEY", ""),
            "doubao": os.environ.get("ARK_API_KEY", ""),
            "zhipu": os.environ.get("ZHIPUAI_API_KEY", ""),
            "kimi": os.environ.get("MOONSHOT_API_KEY", ""),
            "ollama": "",
        }
        self.provider = "anthropic"
        self.model = ""
        self.base_url = ""

        self._proc_a: Optional[SideProcessor] = None
        self._proc_b: Optional[SideProcessor] = None

    def snapshot(self) -> Dict:
        """
        获取当前状态快照。

        Returns:
            包含两侧状态、对比结果和配置的字典
        """
        with self._lock:
            # 基于最新一帧角度的实时对比
            cmp = None
            if self.side_a.angles and self.side_b.angles:
                cmp = compare_sides(self.side_a.angles, self.side_b.angles)
                self.comparison = cmp

            return {
                "side_a": self.side_a.to_dict(),
                "side_b": self.side_b.to_dict(),
                "comparison": cmp or self.comparison,
                "last_advice": self.last_advice,
                "provider": self.provider,
                "model": self.model,
                "api_keys": dict(self.api_keys),
            }

    def start_side(self, which: str):
        """
        启动指定侧的处理线程。

        Args:
            which: 侧标识（"a" 或 "b"）

        Returns:
            (success, message) 元组
        """
        with self._lock:
            side = self.side_a if which == "a" else self.side_b
            if side.running:
                return False, "已在运行"
            if not side.data_loaded:
                return False, "请先装载数据"
            side.running = True

        # 继续追加到现有历史（不清空）
        side._hist_counter = 0
        proc = SideProcessor(side, self._lock)
        if which == "a":
            self._proc_a = proc
        else:
            self._proc_b = proc
        proc.start()
        return True, ""

    def load_data(self, which: str):
        """
        装载数据槽：清空历史、标记已装载，准备接收分析数据。

        Args:
            which: 侧标识（"a" 或 "b"）

        Returns:
            (success, message) 元组
        """
        with self._lock:
            side = self.side_a if which == "a" else self.side_b
            if side.running:
                return False, "分析进行中，请先停止"

        with side.history_lock:
            side.history.clear()
            side.frame_buffer.clear()
        side._hist_counter = 0

        with self._lock:
            side.data_loaded = True
        return True, ""

    def unload_data(self, which: str):
        """
        卸载数据槽：停止分析（如在运行）并清空历史。

        Args:
            which: 侧标识（"a" 或 "b"）

        Returns:
            (success, message) 元组
        """
        self.stop_side(which)
        side = self.side_a if which == "a" else self.side_b
        with side.history_lock:
            side.history.clear()
            side.frame_buffer.clear()
        with self._lock:
            side.data_loaded = False
        return True, ""

    def stop_side(self, which: str):
        """
        停止指定侧的处理线程。

        Args:
            which: 侧标识（"a" 或 "b"）
        """
        proc = self._proc_a if which == "a" else self._proc_b
        side = self.side_a if which == "a" else self.side_b

        if proc:
            proc.stop()
            proc.join(timeout=3)

        from pose.rendering import make_placeholder
        with self._lock:
            side.running = False
            side.latest_frame = make_placeholder(
                text=f"侧 {'A' if which == 'a' else 'B'} — 已停止",
                side='A' if which == 'a' else 'B'
            )

        if which == "a":
            self._proc_a = None
        else:
            self._proc_b = None
