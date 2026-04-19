"""
API 路由模块，
包含所有 Flask API 路由定义
"""
import os
import sys
import time
"""
忘了导入这个拿来干嘛的了
"""
import tempfile
import json
import subprocess
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from io import BytesIO

from flask import request, jsonify, render_template, send_file, Response

import cv2
import numpy as np

# 模块导入
from config.constants import MP_JOINT_DEF, PRESET_MAPS, DEFAULT_C3D_MAP
from data.c3d_loader import C3DLoader
from temporal.timeseries import compare_timeseries
from temporal.alignment import composite_global_align, best_align_joint
from temporal.preprocessing import fill_nan
from .streaming import gen_mjpeg_stream
from .app import get_state

# 可选依赖检测
HAS_EZC3D = False
try:
    import ezc3d
    HAS_EZC3D = True
except ImportError:
    HAS_EZC3D = False


def register_routes(app):
    """
    注册所有 API 路由到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    STATE = get_state()

    @app.route("/")
    def index():
        """主页面路由"""
        return render_template(
            'index.html',
            has_ezc3d=HAS_EZC3D,
            api_keys_json=json.dumps(STATE.api_keys),
            provider=STATE.provider
        )

    @app.route("/feed_a")
    def feed_a():
        """侧 A 视频流"""
        return Response(
            gen_mjpeg_stream(STATE.side_a, STATE._lock),
            mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    @app.route("/feed_b")
    def feed_b():
        """侧 B 视频流"""
        return Response(
            gen_mjpeg_stream(STATE.side_b, STATE._lock),
            mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    @app.route("/api/status")
    def api_status():
        """获取当前状态"""
        return jsonify(STATE.snapshot())

    @app.route("/api/load_data", methods=["POST"])
    def api_load_data():
        """装载数据槽"""
        which = (request.json or {}).get("which", "a")
        ok, msg = STATE.load_data(which)
        return jsonify({"ok": ok, "msg": msg})

    @app.route("/api/unload_data", methods=["POST"])
    def api_unload_data():
        """卸载数据槽"""
        which = (request.json or {}).get("which", "a")
        ok, msg = STATE.unload_data(which)
        return jsonify({"ok": ok, "msg": msg})

    @app.route("/api/start", methods=["POST"])
    def api_start():
        """启动分析"""
        which = (request.json or {}).get("which", "a")
        ok, msg = STATE.start_side(which)
        return jsonify({"ok": ok, "msg": msg})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        """停止分析"""
        which = (request.json or {}).get("which", "a")
        STATE.stop_side(which)
        return jsonify({"ok": True})

    @app.route("/api/set_source", methods=["POST"])
    def api_set_source():
        """设置输入源"""
        d = request.json or {}
        which = d.get("which", "a")
        side = STATE.side_a if which == "a" else STATE.side_b
        with STATE._lock:
            side.source = d.get("source", "camera")
            side.camera_idx = int(d.get("camera_idx", 0))
        return jsonify({"ok": True})

    @app.route("/api/upload_frame", methods=["POST"])
    def api_upload_frame():
        """接收移动端上传的单帧图像"""
        which = request.form.get("which", "a")
        side = STATE.side_a if which == "a" else STATE.side_b

        with STATE._lock:
            if not side.data_loaded or not side.running:
                return jsonify({"ok": False, "msg": "请先装载数据并开始分析"})
            if side.source != "mobile":
                return jsonify({"ok": False, "msg": "非移动端模式"})

        if "file" not in request.files:
            return jsonify({"ok": False, "msg": "无图像数据"})

        f = request.files["file"]
        try:
            arr = np.frombuffer(f.read(), np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return jsonify({"ok": False, "msg": "无法解码图像"})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

        from processing.mobile_processor import process_mobile_frame
        process_mobile_frame(side, frame, STATE._lock, which)
        return jsonify({"ok": True})

    @app.route("/api/upload_video", methods=["POST"])
    def api_upload_video():
        """上传视频文件"""
        which = request.form.get("which", "a")
        if "file" not in request.files:
            return jsonify({"ok": False, "msg": "无文件"})

        f = request.files["file"]
        ext = Path(f.filename).suffix.lower()
        if ext not in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
            return jsonify({"ok": False, "msg": "格式不支持"})

        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        f.save(tmp.name)
        tmp.close()

        side = STATE.side_a if which == "a" else STATE.side_b
        cap = cv2.VideoCapture(tmp.name)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        with STATE._lock:
            side.video_path = tmp.name
            side.source = "video"

        return jsonify({
            "ok": True,
            "filename": f.filename,
            "n_frames": n,
            "fps": round(fps, 1)
        })

    @app.route("/api/upload_c3d", methods=["POST"])
    def api_upload_c3d():
        """上传 C3D 文件"""
        if not HAS_EZC3D:
            return jsonify({"ok": False, "msg": "请先安装 ezc3d"})

        which = request.form.get("which", "a")
        if "file" not in request.files:
            return jsonify({"ok": False, "msg": "无文件"})

        f = request.files["file"]
        if not f.filename.lower().endswith(".c3d"):
            return jsonify({"ok": False, "msg": "需要 .c3d 文件"})

        preset = request.form.get("preset", "vicon_pig")
        custom = request.form.get("custom_map", "").strip()

        try:
            marker_map = json.loads(custom) if custom else PRESET_MAPS.get(preset, DEFAULT_C3D_MAP)
            tmp = tempfile.NamedTemporaryFile(suffix=".c3d", delete=False)
            f.save(tmp.name)
            tmp.close()

            loader = C3DLoader(tmp.name, marker_map)
            side = STATE.side_a if which == "a" else STATE.side_b

            with STATE._lock:
                side.c3d_loader = loader
                side.c3d_name = f.filename
                side.source = "c3d"
                side.c3d_frame = 0

            return jsonify({
                "ok": True,
                "filename": f.filename,
                "n_frames": loader.n_frames,
                "fps": loader.fps,
                "loaded_joints": loader.loaded_joints,
                "missing_joints": loader.missing_joints,
                "which": which
            })
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    @app.route("/api/clear_c3d", methods=["POST"])
    def api_clear_c3d():
        """清除 C3D 文件"""
        which = (request.json or {}).get("which", "a")
        side = STATE.side_a if which == "a" else STATE.side_b
        with STATE._lock:
            side.c3d_loader = None
            side.c3d_name = ""
            side.source = "camera"
        return jsonify({"ok": True})

    @app.route("/api/set_apikey", methods=["POST"])
    def api_set_apikey():
        """设置 API 密钥"""
        d = request.json or {}
        with STATE._lock:
            STATE.api_keys[d.get("provider", "anthropic")] = d.get("api_key", "").strip()
        return jsonify({"ok": True})

    @app.route("/api/set_provider", methods=["POST"])
    def api_set_provider():
        """设置 AI 提供商"""
        d = request.json or {}
        with STATE._lock:
            STATE.provider = d.get("provider", "anthropic")
            STATE.model = d.get("model", "").strip()
            STATE.base_url = d.get("base_url", "").strip()
        return jsonify({"ok": True})

    @app.route("/api/advice", methods=["POST"])
    def api_advice():
        """获取 AI 建议"""
        from ai.providers import call_ai

        extra = (request.json or {}).get("extra", "")

        # 获取完整历史数据，用于构建时序 Prompt
        with STATE.side_a.history_lock:
            hist_a = list(STATE.side_a.history)
        with STATE.side_b.history_lock:
            hist_b = list(STATE.side_b.history)
        with STATE._lock:
            sym_a = dict(STATE.side_a.symmetry)
            sym_b = dict(STATE.side_b.symmetry)

        if len(hist_a) < 5:
            return jsonify({"ok": False, "msg": "侧A历史数据不足，请先录制/分析至少几秒"})
        if len(hist_b) < 5:
            return jsonify({"ok": False, "msg": "侧B历史数据不足，请先录制/分析至少几秒"})

        # 将时间戳归一化为相对秒数
        def rel(hist):
            if not hist:
                return hist
            t0 = hist[0]["t"]
            return [{**h, "t": round(h["t"] - t0, 3)} for h in hist]

        # 计算时序对比结果供 Prompt 使用
        ts_result = compare_timeseries(rel(hist_a), rel(hist_b))

        advice = call_ai(ts_result, rel(hist_a), rel(hist_b), sym_a, sym_b, extra)
        with STATE._lock:
            STATE.last_advice = advice
        return jsonify({"ok": True, "advice": advice})

    @app.route("/api/install_ezc3d", methods=["POST"])
    def api_install_ezc3d():
        """安装 ezc3d 包"""
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "ezc3d", "--quiet"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if r.returncode == 0:
                return jsonify({"ok": True, "msg": "安装成功，请重启程序"})
            return jsonify({"ok": False, "msg": r.stderr[-300:]})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    @app.route("/api/history")
    def api_history():
        """获取历史数据"""
        which = request.args.get("which", "a")
        limit = min(int(request.args.get("limit", 600)), 1800)
        side = STATE.side_a if which == "a" else STATE.side_b
        with side.history_lock:
            data = list(side.history)[-limit:]

        # 相对时间戳归一化（相对于首帧）
        if data:
            t0 = data[0]["t"]
            for d in data:
                d["t"] = round(d["t"] - t0, 2)

        side2 = STATE.side_a if which == "a" else STATE.side_b
        with side2.history_lock:
            has_frames = len(side2.frame_buffer) > 0

        return jsonify({
            "ok": True,
            "which": which,
            "data": data,
            "has_frames": has_frames,
            "joint_keys": list(MP_JOINT_DEF.keys())
        })

    @app.route("/api/compare_ts")
    def api_compare_ts():
        """基于完整时序的双侧对比端点，返回 DTW 对齐评分"""
        with STATE.side_a.history_lock:
            hist_a = list(STATE.side_a.history)
        with STATE.side_b.history_lock:
            hist_b = list(STATE.side_b.history)

        # 将时间戳归一化为相对秒数
        def normalise(hist):
            if not hist:
                return hist
            t0 = hist[0]["t"]
            return [{**h, "t": round(h["t"] - t0, 3)} for h in hist]

        result = compare_timeseries(normalise(hist_a), normalise(hist_b))
        return jsonify(result)

    @app.route("/api/aligned_series")
    def api_aligned_series():
        """返回各关节对齐后的角度序列及对应的骨架帧坐标"""
        with STATE.side_a.history_lock:
            hist_a = list(STATE.side_a.history)
        with STATE.side_b.history_lock:
            hist_b = list(STATE.side_b.history)

        def rel(h):
            if not h:
                return h
            t0 = h[0]["t"]
            return [{**x, "t": round(x["t"] - t0, 3)} for x in h]

        hist_a = rel(hist_a)
        hist_b = rel(hist_b)

        MIN = 15
        if len(hist_a) < MIN or len(hist_b) < MIN:
            return jsonify({
                "ok": False,
                "reason": f"需要至少{MIN}帧（A:{len(hist_a)} B:{len(hist_b)}）"
            })

        N_PTS = 200
        joint_keys = list(MP_JOINT_DEF.keys())
        aligned_joints = {}

        # 各关节独立对齐用于评分
        for k in joint_keys:
            va = np.array([h["angles"].get(k, np.nan) for h in hist_a], dtype=float)
            vb = np.array([h["angles"].get(k, np.nan) for h in hist_b], dtype=float)
            fa = fill_nan(va)
            fb = fill_nan(vb)
            if fa is None or fb is None:
                continue
            aln = best_align_joint(fa, fb, n_pts=N_PTS)
            aligned_joints[k] = {
                "cn_name": MP_JOINT_DEF[k][3],
                "a": [round(float(v), 1) for v in aln["a_aligned"]],
                "b": [round(float(v), 1) for v in aln["b_aligned"]],
            }

        if not aligned_joints:
            return jsonify({"ok": False, "reason": "无共同可用关节"})

        # 两阶段全局对齐
        g_aln = composite_global_align(hist_a, hist_b, n_pts=N_PTS)
        frame_a_idx = g_aln["frame_a"]
        frame_b_idx = g_aln["frame_b"]
        n_a, n_b = len(hist_a), len(hist_b)

        lm_a = [hist_a[min(ia, n_a - 1)].get("lm", []) for ia in frame_a_idx]
        lm_b = [hist_b[min(ib, n_b - 1)].get("lm", []) for ib in frame_b_idx]

        # 录制时长信息
        dur_a = round(hist_a[-1]["t"] - hist_a[0]["t"], 2) if len(hist_a) > 1 else 0
        dur_b = round(hist_b[-1]["t"] - hist_b[0]["t"], 2) if len(hist_b) > 1 else 0

        return jsonify({
            "ok": True,
            "n_pts": N_PTS,
            "joints": aligned_joints,
            "global_a_off": g_aln["a_off"],
            "global_b_off": g_aln["b_off"],
            "global_r": round(g_aln.get("r", 0.0), 3) if "r" in g_aln else 0,
            "lm_a": lm_a,
            "lm_b": lm_b,
            "dur_a": dur_a,
            "dur_b": dur_b,
            "n_a": n_a,
            "n_b": n_b,
        })

    @app.route("/api/frame")
    def api_frame():
        """获取指定帧的缩略图"""
        which = request.args.get("which", "a")
        idx = int(request.args.get("idx", 0))
        side = STATE.side_a if which == "a" else STATE.side_b
        with side.history_lock:
            buf_list = list(side.frame_buffer)
        if not buf_list or idx < 0 or idx >= len(buf_list):
            return Response(b"", mimetype="image/jpeg", status=204)
        frame_bytes = buf_list[idx]
        if not frame_bytes:
            return Response(b"", mimetype="image/jpeg", status=204)
        return Response(frame_bytes, mimetype="image/jpeg", headers={"Cache-Control": "no-cache"})

    @app.route("/api/clear_history", methods=["POST"])
    def api_clear_history():
        """清除历史数据"""
        which = (request.json or {}).get("which", "both")
        if which in ("a", "both"):
            with STATE.side_a.history_lock:
                STATE.side_a.history.clear()
                STATE.side_a.frame_buffer.clear()
            STATE.side_a._hist_counter = 0
        if which in ("b", "both"):
            with STATE.side_b.history_lock:
                STATE.side_b.history.clear()
                STATE.side_b.frame_buffer.clear()
            STATE.side_b._hist_counter = 0
        return jsonify({"ok": True})

    @app.route("/api/export_report")
    def api_export_report():
        """导出分析报告"""
        snap = STATE.snapshot()
        snap["generated_at"] = datetime.now().isoformat()
        buf = BytesIO(json.dumps(snap, ensure_ascii=False, indent=2).encode())
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"dance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mimetype="application/json"
        )


def open_browser():
    """在浏览器中打开应用"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")
