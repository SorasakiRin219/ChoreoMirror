"""
舞蹈动作分析系统 v3.0
运行: python app.py  (浏览器自动打开)
"""
import os, sys, json, time, threading, tempfile, webbrowser, warnings, urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import cv2, numpy as np, mediapipe as mp
warnings.filterwarnings("ignore")

try:    import anthropic as _anthropic_mod;  HAS_ANTHROPIC = True
except: HAS_ANTHROPIC = False
try:    import openai as _openai_mod;        HAS_OPENAI = True
except: HAS_OPENAI = False
try:    import ezc3d as _ezc3d_mod;          HAS_EZC3D = True
except: HAS_EZC3D = False
try:    from flask import Flask, Response, request, jsonify, send_file; import io
except: print("\n❌ pip install flask\n"); sys.exit(1)

# ══════════════════════════════════════════════════════════════
#  MediaPipe Tasks API
# ══════════════════════════════════════════════════════════════
from mediapipe.tasks import python as _mp_tasks
from mediapipe.tasks.python import vision as _mp_vision

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pose_landmarker_lite.task")
MODEL_URL  = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
              "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")

def ensure_model():
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100_000: return
    print("[INFO] Downloading pose model (~3 MB)...")
    try:    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH); print("[OK]   Model ready.")
    except Exception as e: print("[ERROR]", e); sys.exit(1)

POSE_CONNECTIONS = [
    (11,13),(13,15),(15,17),(15,19),(17,19),(12,14),(14,16),(16,18),(16,20),(18,20),
    (11,12),(11,23),(12,24),(23,24),(23,25),(25,27),(27,29),(27,31),(29,31),
    (24,26),(26,28),(28,30),(28,32),(30,32),
]

# ══════════════════════════════════════════════════════════════
#  关节定义
# ══════════════════════════════════════════════════════════════
MP_JOINT_DEF: Dict[str,Tuple] = {
    "left_elbow":     (11,13,15,"左肘"),  "right_elbow":    (12,14,16,"右肘"),
    "left_shoulder":  (13,11,23,"左肩"),  "right_shoulder": (14,12,24,"右肩"),
    "left_hip":       (11,23,25,"左髋"),  "right_hip":      (12,24,26,"右髋"),
    "left_knee":      (23,25,27,"左膝"),  "right_knee":     (24,26,28,"右膝"),
    "left_ankle":     (25,27,31,"左踝"),  "right_ankle":    (26,28,32,"右踝"),
    "left_wrist":     (13,15,17,"左腕"),  "right_wrist":    (14,16,18,"右腕"),
}
DEFAULT_C3D_MAP: Dict[str,Dict] = {
    "left_elbow":     {"markers":["LSHO","LELB","LWRA"],"cn_name":"左肘"},
    "right_elbow":    {"markers":["RSHO","RELB","RWRA"],"cn_name":"右肘"},
    "left_shoulder":  {"markers":["LELB","LSHO","LHIP"],"cn_name":"左肩"},
    "right_shoulder": {"markers":["RELB","RSHO","RHIP"],"cn_name":"右肩"},
    "left_hip":       {"markers":["LSHO","LHIP","LKNE"],"cn_name":"左髋"},
    "right_hip":      {"markers":["RSHO","RHIP","RKNE"],"cn_name":"右髋"},
    "left_knee":      {"markers":["LHIP","LKNE","LANK"],"cn_name":"左膝"},
    "right_knee":     {"markers":["RHIP","RKNE","RANK"],"cn_name":"右膝"},
    "left_ankle":     {"markers":["LKNE","LANK","LTOE"],"cn_name":"左踝"},
    "right_ankle":    {"markers":["RKNE","RANK","RTOE"],"cn_name":"右踝"},
    "left_wrist":     {"markers":["LELB","LWRA","LFIN"],"cn_name":"左腕"},
    "right_wrist":    {"markers":["RELB","RWRA","RFIN"],"cn_name":"右腕"},
}
PRESET_MAPS = {
    "vicon_pig": DEFAULT_C3D_MAP,
    "c3d_generic": {
        "left_elbow":     {"markers":["L.Shoulder","L.Elbow","L.Wrist"],"cn_name":"左肘"},
        "right_elbow":    {"markers":["R.Shoulder","R.Elbow","R.Wrist"],"cn_name":"右肘"},
        "left_shoulder":  {"markers":["L.Elbow","L.Shoulder","L.Hip"],"cn_name":"左肩"},
        "right_shoulder": {"markers":["R.Elbow","R.Shoulder","R.Hip"],"cn_name":"右肩"},
        "left_hip":       {"markers":["L.Shoulder","L.Hip","L.Knee"],"cn_name":"左髋"},
        "right_hip":      {"markers":["R.Shoulder","R.Hip","R.Knee"],"cn_name":"右髋"},
        "left_knee":      {"markers":["L.Hip","L.Knee","L.Ankle"],"cn_name":"左膝"},
        "right_knee":     {"markers":["R.Hip","R.Knee","R.Ankle"],"cn_name":"右膝"},
        "left_ankle":     {"markers":["L.Knee","L.Ankle","L.Toe"],"cn_name":"左踝"},
        "right_ankle":    {"markers":["R.Knee","R.Ankle","R.Toe"],"cn_name":"右踝"},
        "left_wrist":     {"markers":["L.Elbow","L.Wrist","L.Finger"],"cn_name":"左腕"},
        "right_wrist":    {"markers":["R.Elbow","R.Wrist","R.Finger"],"cn_name":"右腕"},
    },
}

# ══════════════════════════════════════════════════════════════
#  核心数学
# ══════════════════════════════════════════════════════════════
def calculate_angle(a,b,c) -> float:
    ba,bc = np.asarray(a)-np.asarray(b), np.asarray(c)-np.asarray(b)
    n = np.linalg.norm(ba)*np.linalg.norm(bc)
    return float(np.degrees(np.arccos(np.clip(np.dot(ba,bc)/n,-1,1)))) if n>1e-9 else 0.0

def deviation_grade(d:float)->str:
    if d<=5: return "excellent"
    if d<=15: return "good"
    if d<=30: return "warning"
    return "poor"

def score_from_dev(d:float)->float: return float(100*np.exp(-d/25))

def extract_mp_angles(landmarks, w:int, h:int)->Dict:
    lm=landmarks; out={}
    for key,(ai,bi,ci,cn) in MP_JOINT_DEF.items():
        try:
            vis=min(lm[ai].visibility or 0,lm[bi].visibility or 0,lm[ci].visibility or 0)
            if vis<0.45: continue
            def pt(i,_l=lm): return np.array([_l[i].x*w,_l[i].y*h])
            out[key]={"angle":round(calculate_angle(pt(ai),pt(bi),pt(ci)),1),"cn_name":cn,"visibility":round(vis,2)}
        except: pass
    return out

def analyze_symmetry(angles:Dict)->Dict:
    pairs=[("left_elbow","right_elbow","肘关节"),("left_shoulder","right_shoulder","肩关节"),
           ("left_hip","right_hip","髋关节"),("left_knee","right_knee","膝关节"),
           ("left_ankle","right_ankle","踝关节")]
    r={}
    for l,ri,n in pairs:
        if l in angles and ri in angles:
            d=abs(angles[l]["angle"]-angles[ri]["angle"])
            r[n]={"left":angles[l]["angle"],"right":angles[ri]["angle"],"diff":round(d,1),"symmetric":d<15}
    return r

def compare_sides(a_angles:Dict, b_angles:Dict)->Dict:
    """逐关节比较 A（学生）与 B（参考）的单帧角度差异，返回各关节偏差与综合评分"""
    joints,scores=[],[]
    for key,info in a_angles.items():
        if key not in b_angles: continue
        ref_angle = b_angles[key]["angle"] if isinstance(b_angles[key],dict) else b_angles[key]
        dev=abs(info["angle"]-ref_angle)
        sc=score_from_dev(dev)
        joints.append((key,{
            "current":info["angle"],"standard":round(ref_angle,1),
            "deviation":round(dev,1),"grade":deviation_grade(dev),
            "score":round(sc,1),"cn_name":info["cn_name"],
            "direction":"偏大" if info["angle"]>ref_angle else "偏小",
        }))
        scores.append(sc)
    return {"joints":dict(joints),"overall_score":round(float(np.mean(scores)),1) if scores else 0.0}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  时序对比:包含DTW + 最优时间对齐 + 幅度归一化
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _fill_nan(arr: np.ndarray) -> Optional[np.ndarray]:
    """线性插值填充内部 NaN，首尾向外填充；有效点不足 3 个时返回 None"""
    valid = ~np.isnan(arr)
    if valid.sum() < 3:
        return None
    out = arr.copy()
    idx = np.arange(len(arr))
    out[~valid] = np.interp(idx[~valid], idx[valid], arr[valid])
    return out


def _resample(arr: np.ndarray, n: int) -> np.ndarray:
    """通过线性插值将数组重采样为精确 n 个点。"""
    if len(arr) == n:
        return arr
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(arr)), arr)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  两阶段对齐：
#  阶段一 — 滑动窗口找最优起始点 (a_off, b_off)
#  阶段二 — DTW 规整路径实现分段速度归一
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _dtw_path(a: np.ndarray, b: np.ndarray, band_frac: float = 0.3
              ) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    完整 DTW：带回溯，输出规整路径。

    参数
    ----
    a, b       : 两条一维序列（长度可以不同）
    band_frac  : Sakoe-Chiba 带宽，占 max(len_a,len_b) 的比例

    返回
    ----
    dist       : 归一化 DTW 距离
    path_i     : A 的帧索引数组  (沿规整路径等密度采样 N_PATH 点)
    path_j     : B 的帧索引数组  (与 path_i 对应)

    路径意义：path_i[k] 和 path_j[k] 是"同一个动作时刻"的帧。
    """
    na, nb = len(a), len(b)
    band   = max(3, int(max(na, nb) * band_frac))
    INF    = 1e18

    # ── 前向 DP ─────────────────────────────────────────────────
    D = np.full((na, nb), INF)
    D[0, 0] = (a[0] - b[0]) ** 2
    for j in range(1, min(band + 1, nb)):
        D[0, j] = D[0, j-1] + (a[0] - b[j]) ** 2
    for i in range(1, na):
        lo = max(0, i - band)
        hi = min(nb - 1, i + band)
        for j in range(lo, hi + 1):
            cost = (a[i] - b[j]) ** 2
            D[i, j] = cost + min(
                D[i-1, j],
                D[i, j-1]   if j > lo  else INF,
                D[i-1, j-1] if j > lo  else INF,
            )

    dist = float(D[na-1, nb-1]) / (na + nb) if D[na-1, nb-1] < INF else INF

    # ── 回溯 → 规整路径 ─────────────────────────────────────────
    path_raw = []
    i, j = na - 1, nb - 1
    while i > 0 or j > 0:
        path_raw.append((i, j))
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            best = min((D[i-1, j-1], i-1, j-1),
                       (D[i-1, j],   i-1, j),
                       (D[i,   j-1], i,   j-1))
            i, j = best[1], best[2]
    path_raw.append((0, 0))
    path_raw.reverse()

    # 沿路径均匀采样 N_PATH 个点（保证 path_i/path_j 长度固定）
    N_PATH = 200
    path_arr  = np.array(path_raw)          # shape (L, 2)
    L         = len(path_arr)
    idx_f     = np.linspace(0, L - 1, N_PATH)
    path_i    = np.round(np.interp(idx_f, np.arange(L), path_arr[:, 0])).astype(int)
    path_j    = np.round(np.interp(idx_f, np.arange(L), path_arr[:, 1])).astype(int)
    path_i    = np.clip(path_i, 0, na - 1)
    path_j    = np.clip(path_j, 0, nb - 1)

    return dist, path_i, path_j


def _best_start(comp_a: np.ndarray, comp_b: np.ndarray,
                n_pts: int, n_steps: int = 40) -> Tuple[int, int]:
    """
    阶段一：用合成信号（z-score 均值）的滑动相关找到最优起始帧。

    穷举两侧各自的起始偏移：
      a_off ∈ [0, na//3]  （A 最多跳过前 1/3）
      b_off ∈ [0, nb//3]  （B 最多跳过前 1/3）
    比较长度 = min(na-a_off, nb-b_off)，不再做整体速度缩放。
    速度差异完全交由后续 DTW 路径处理。

    返回 (a_off, b_off)。
    """
    na, nb = len(comp_a), len(comp_b)
    a_steps = max(1, round(na * 0.33) // max(n_steps // 2, 1))
    b_steps = max(1, round(nb * 0.33) // max(n_steps // 2, 1))

    best_r   = -np.inf
    best_off = (0, 0)

    for a_off in range(0, round(na * 0.33) + 1, a_steps):
        for b_off in range(0, round(nb * 0.33) + 1, b_steps):
            w = min(na - a_off, nb - b_off)
            if w < max(10, n_pts // 4):
                continue
            av = comp_a[a_off: a_off + w]
            bv = comp_b[b_off: b_off + w]
            sa, sb = av.std(), bv.std()
            if sa < 1e-6 or sb < 1e-6:
                r = 0.0
            else:
                r = float(np.corrcoef(av, bv)[0, 1])
                if np.isnan(r): r = 0.0
            if r > best_r:
                best_r   = r
                best_off = (a_off, b_off)

    return best_off


def _composite_global_align(hist_a: list, hist_b: list,
                             n_pts: int = 200) -> dict:
    """
    全局两阶段对齐（作用于骨架帧映射）：
      阶段一：滑动窗口找最优 (a_off, b_off) 起始帧
      阶段二：DTW 规整路径给出分段速度归一的 (path_i, path_j)

    path_i[k] 是 A 在对齐段内的帧偏移，path_j[k] 对应 B 的帧偏移。
    骨架映射：
      original_A_frame[k] = a_off + path_i[k]  (映射回 hist_a 索引)
      original_B_frame[k] = b_off + path_j[k]  (映射回 hist_b 索引)
    """
    JOINT_KEYS = list(MP_JOINT_DEF.keys())
    n_a = len(hist_a)
    n_b = len(hist_b)

    def build_composite(hist, nk):
        mats = []
        for k in JOINT_KEYS:
            arr = np.array([h["angles"].get(k, np.nan) for h in hist], dtype=float)
            arr = _fill_nan(arr)
            if arr is None: continue
            arr = _resample(arr, nk)
            s   = arr.std()
            if s < 1.0: continue
            mats.append((arr - arr.mean()) / s)
        return np.mean(mats, axis=0) if mats else np.zeros(nk)

    comp_a = build_composite(hist_a, n_a)   # 原始帧数，不重采样
    comp_b = build_composite(hist_b, n_b)

    # 阶段一：找最优起始帧（以原始帧数索引）
    a_off, b_off = _best_start(comp_a, comp_b, n_pts=n_pts, n_steps=40)

    # 提取对齐段
    seg_a = comp_a[a_off:]
    seg_b = comp_b[b_off:]

    # 阶段二：DTW 规整路径
    _, path_i, path_j = _dtw_path(seg_a, seg_b, band_frac=0.35)

    # path_i / path_j 是段内偏移，转为 hist 原始索引
    frame_a = np.clip(a_off + path_i, 0, n_a - 1).tolist()
    frame_b = np.clip(b_off + path_j, 0, n_b - 1).tolist()

    return {
        "a_off":   a_off,
        "b_off":   b_off,
        "frame_a": frame_a,   # 长度 N_PATH=200，每个是 hist_a 的帧索引
        "frame_b": frame_b,   # 同上，对应 hist_b
        "n_pts":   200,
    }


def _best_align_joint(a_raw: np.ndarray, b_raw: np.ndarray,
                      n_pts: int = 200) -> dict:
    """
    单关节两阶段对齐：
      阶段一：滑动窗口找最优起始偏移 (a_off, b_off)
      阶段二：DTW 规整路径沿路径采样，得到真正分段速度归一的对齐序列

    a_aligned / b_aligned 是沿 DTW 路径采样的角度序列：
    a_aligned[k] 和 b_aligned[k] 对应动作的"同一时刻"。
    """
    na, nb = len(a_raw), len(b_raw)

    def znorm(x):
        s = x.std()
        return (x - x.mean()) / s if s > 0.5 else x - x.mean()

    a_z = znorm(a_raw)
    b_z = znorm(b_raw)

    # 阶段一：滑窗找起始点
    a_off, b_off = _best_start(a_z, b_z, n_pts=n_pts, n_steps=40)

    seg_az = a_z[a_off:]
    seg_bz = b_z[b_off:]

    # 阶段二：DTW 规整路径
    dtw_d, path_i, path_j = _dtw_path(seg_az, seg_bz, band_frac=0.35)

    # 沿路径采样原始角度序列 → 这就是分段速度归一后的对齐结果
    a_aln = a_raw[a_off:][np.clip(path_i, 0, len(seg_az) - 1)]
    b_aln = b_raw[b_off:][np.clip(path_j, 0, len(seg_bz) - 1)]

    rmsd = float(np.sqrt(np.mean((a_aln - b_aln) ** 2)))

    # Pearson r 在 z-score 对齐序列上计算
    az_samp = znorm(a_aln)
    bz_samp = znorm(b_aln)
    sa, sb  = az_samp.std(), bz_samp.std()
    if sa < 1e-6 or sb < 1e-6:
        r = 0.0
    else:
        r = float(np.corrcoef(az_samp, bz_samp)[0, 1])
        if np.isnan(r): r = 0.0

    return {
        "a_off":     a_off,
        "b_off":     b_off,
        "scale":     round(nb / max(na, 1), 3),
        "r":         round(r, 3),
        "dtw":       round(dtw_d, 4),
        "rmsd":      round(rmsd, 1),
        "a_aligned": a_aln,
        "b_aligned": b_aln,
    }


def _segment_diff(a_aligned: np.ndarray, b_aligned: np.ndarray,
                  n_segs: int = 4) -> List[dict]:
    """
    将对齐后的序列等分为 n_segs 个时间窗口，
    每段返回 {t_start, t_end, mean_a, mean_b, diff, direction}
    """
    n = len(a_aligned)
    segs = []
    for i in range(n_segs):
        s = i * n // n_segs
        e = (i + 1) * n // n_segs
        ma = float(np.mean(a_aligned[s:e]))
        mb = float(np.mean(b_aligned[s:e]))
        segs.append({
            "t_start":   round(i / n_segs, 2),
            "t_end":     round((i + 1) / n_segs, 2),
            "mean_a":    round(ma, 1),
            "mean_b":    round(mb, 1),
            "diff":      round(ma - mb, 1),
            "direction": "偏大" if ma > mb else "偏小",
        })
    return segs


def compare_timeseries(hist_a: list, hist_b: list) -> Dict:
    """
    两阶段时序对比（滑窗起始点 + DTW 分段速度归一）。

    每个关节：
      1. _best_align_joint()：找起始点 → DTW 路径 → 对齐序列
      2. _segment_diff()：分段角度差
      3. 综合评分 = 0.45×r分 + 0.35×DTW分 + 0.20×RMSD分
    """
    MIN_FRAMES = 15
    if len(hist_a) < MIN_FRAMES or len(hist_b) < MIN_FRAMES:
        return {"ok": False,
                "reason": f"需要至少{MIN_FRAMES}帧（当前 A:{len(hist_a)} B:{len(hist_b)}）",
                "overall_score": 0.0, "joints": {},
                "n_a": len(hist_a), "n_b": len(hist_b)}

    joint_keys = list(MP_JOINT_DEF.keys())
    N_PTS = 200

    joints_out: Dict = {}
    scores: List[float] = []

    for k in joint_keys:
        va = np.array([h["angles"].get(k, np.nan) for h in hist_a], dtype=float)
        vb = np.array([h["angles"].get(k, np.nan) for h in hist_b], dtype=float)
        fa = _fill_nan(va)
        fb = _fill_nan(vb)
        if fa is None or fb is None:
            continue

        aln = _best_align_joint(fa, fb, n_pts=N_PTS)

        r     = aln["r"]
        dtw_d = aln["dtw"]
        rmsd  = aln["rmsd"]

        r_score    = 50.0 * (r + 1.0)
        dtw_score  = 100.0 * float(np.exp(-dtw_d / 0.8))
        rmsd_score = 100.0 * float(np.exp(-rmsd / 25.0))
        score      = round(0.45 * r_score + 0.35 * dtw_score + 0.20 * rmsd_score, 1)

        if score >= 85:   grade = "excellent"
        elif score >= 68: grade = "good"
        elif score >= 45: grade = "warning"
        else:             grade = "poor"

        segs     = _segment_diff(aln["a_aligned"], aln["b_aligned"], n_segs=4)
        diffs    = [abs(s["diff"]) for s in segs]
        peak_seg = segs[int(np.argmax(diffs))]

        cn = MP_JOINT_DEF[k][3]
        joints_out[k] = {
            "cn_name":   cn,
            "score":     score,
            "grade":     grade,
            "r":         round(r, 3),
            "rmsd":      round(rmsd, 1),
            "dtw_score": round(dtw_score, 1),
            "scale":     aln["scale"],
            "mean_a":    round(float(np.mean(aln["a_aligned"])), 1),
            "mean_b":    round(float(np.mean(aln["b_aligned"])), 1),
            "segments":  segs,
            "peak_diff": {
                "t_label":   f"{round(peak_seg['t_start']*100)}%–{round(peak_seg['t_end']*100)}%",
                "diff":      peak_seg["diff"],
                "mean_a":    peak_seg["mean_a"],
                "mean_b":    peak_seg["mean_b"],
                "direction": peak_seg["direction"],
            },
        }
        scores.append(score)

    if not scores:
        return {"ok": False, "reason": "双侧无共同可用关节",
                "overall_score": 0.0, "joints": {},
                "n_a": len(hist_a), "n_b": len(hist_b)}

    return {
        "ok":            True,
        "overall_score": round(float(np.mean(scores)), 1),
        "joints":        joints_out,
        "n_a":           len(hist_a),
        "n_b":           len(hist_b),
        "n_pts":         N_PTS,
    }


# ══════════════════════════════════════════════════════════════
#  C3D 加载器
# ══════════════════════════════════════════════════════════════
class C3DLoader:
    def __init__(self, path:str, marker_map:Dict=None):
        self.path=path; self.marker_map=marker_map or DEFAULT_C3D_MAP
        self.fps=100.0; self.n_frames=0
        self.angle_seq:Dict[str,np.ndarray]={}; self.mean_angles:Dict[str,float]={}
        self._marker_data:Dict[str,np.ndarray]={}; self._marker_xyz_raw:Dict[str,np.ndarray]={}
        self.loaded_joints:List[str]=[]; self.missing_joints:List[str]=[]
        self.available_markers:List[str]=[]
        self._load()

    def _load(self):
        import ezc3d
        c3d=ezc3d.c3d(self.path); self.fps=float(c3d["header"]["points"]["frame_rate"])
        labels=[l.strip() for l in c3d["parameters"]["POINT"]["LABELS"]["value"]]
        data=c3d["data"]["points"]; self.n_frames=data.shape[2]
        self.available_markers=labels
        for i,label in enumerate(labels):
            xyz=data[:3,i,:].T.copy()
            xyz[np.all(np.abs(xyz)<1e-6,axis=1)]=np.nan
            self._marker_data[label]=xyz
        available=set(labels)
        for jk,jdef in self.marker_map.items():
            resolved=[]
            for m in jdef["markers"]:
                r=m if m in available else next((a for a in available if a.upper()==m.upper()),None)
                resolved.append(r)
            if any(r is None for r in resolved): self.missing_joints.append(jk); continue
            seq=np.full(self.n_frames,np.nan)
            for f in range(self.n_frames):
                pts=[self._marker_data[r][f] for r in resolved]
                if any(np.any(np.isnan(p)) for p in pts): continue
                seq[f]=calculate_angle(pts[0],pts[1],pts[2])
            if len(seq[~np.isnan(seq)])<5: self.missing_joints.append(jk); continue
            self.angle_seq[jk]=seq; self.mean_angles[jk]=float(np.nanmean(seq))
            self.loaded_joints.append(jk)

    def get_frame_angles(self, f:int)->Dict[str,float]:
        f=max(0,min(f,self.n_frames-1))
        return {k:float(v[f]) for k,v in self.angle_seq.items() if not np.isnan(v[f])}

    def get_mean_angles(self)->Dict[str,float]: return dict(self.mean_angles)

    def render_frame(self, f:int, w:int=480, h:int=360, label:str="C3D")->np.ndarray:
        """将 C3D 3D 标记点数据渲染为棒状人体角度条形图。"""
        canvas=np.zeros((h,w,3),np.uint8); canvas[:]=( 8,16,28)
        angles=self.get_frame_angles(f)
        GRADE_CLR={"excellent":(0,210,80),"good":(0,200,200),"warning":(0,165,255),"poor":(30,30,220)}
        # 绘制角度条形图
        bar_x=16; bar_y=44; bw=w-32; bh=14; gap=22
        cv2.putText(canvas,f"{label}  Frame {f}/{self.n_frames-1}",(8,22),
                    cv2.FONT_HERSHEY_SIMPLEX,0.5,(80,180,255),1,cv2.LINE_AA)
        for i,(key,ang) in enumerate(angles.items()):
            y=bar_y+i*gap; cn=MP_JOINT_DEF.get(key,("","","",key))[3]
            color=(0,160,200)
            fill=max(1,int(ang/180*bw))
            cv2.rectangle(canvas,(bar_x,y),(bar_x+bw,y+bh),(25,35,50),-1)
            cv2.rectangle(canvas,(bar_x,y),(bar_x+fill,y+bh),color,-1)
            cv2.putText(canvas,f"{cn}: {ang:.0f}°",(bar_x+2,y+11),
                        cv2.FONT_HERSHEY_SIMPLEX,0.37,(200,200,200),1,cv2.LINE_AA)
        ts=f" {f/self.fps:.1f}s"
        cv2.putText(canvas,ts,(w-60,h-8),cv2.FONT_HERSHEY_SIMPLEX,0.38,(60,80,100),1,cv2.LINE_AA)
        return canvas

    def angles_to_mp_format(self, f:int)->Dict:
        raw=self.get_frame_angles(f)
        return {k:{"angle":v,"cn_name":MP_JOINT_DEF[k][3],"visibility":1.0}
                for k,v in raw.items() if k in MP_JOINT_DEF}

# ══════════════════════════════════════════════════════════════
#  绘制工具
# ══════════════════════════════════════════════════════════════
GRADE_BGR={"excellent":(0,210,80),"good":(0,200,200),"warning":(0,165,255),"poor":(30,30,220)}

def make_placeholder(w=480, h=360, text="等待开始...", side="") -> np.ndarray:
    """
    深海军蓝+紫色占位画布
    A 侧为天蓝色，B 侧为紫色
    """
    is_b = (str(side).upper() == "B")

    # BGR 颜色元组
    CYAN   = (255, 178, 56)    # #38b2ff
    VIOLET = (250, 139, 167)   # #a78bfa
    accent = VIOLET if is_b else CYAN

    BG_DEEP  = (26, 14, 8)     # #080e1a  深海军蓝
    BG_CARD  = (53, 22, 13)    # #0d1626
    GRID_CLR = (64, 46, 23)    # 点阵网格颜色

    img = np.full((h, w, 3), BG_DEEP, np.uint8)

    # ── 点阵网格背景 ────────────────────────────────────────────
    for x in range(0, w, 28):
        for y in range(0, h, 28):
            cv2.circle(img, (x, y), 1, GRID_CLR, -1, cv2.LINE_AA)

    # ── 骨架背后的径向光晕 ──────────────────────────────────────
    cx, cy = w // 2, int(h * 0.40)
    glow_r = int(min(w, h) * 0.38)
    for r in range(glow_r, 0, -4):
        alpha = 0.018 * (1 - r / glow_r)
        col = (
            int(BG_DEEP[0] + (accent[0] - BG_DEEP[0]) * alpha * 6),
            int(BG_DEEP[1] + (accent[1] - BG_DEEP[1]) * alpha * 6),
            int(BG_DEEP[2] + (accent[2] - BG_DEEP[2]) * alpha * 6),
        )
        cv2.circle(img, (cx, cy), r, col, 2, cv2.LINE_AA)

    # ── 骨架轮廓 ────────────────────────────────────────────────
    scale = min(w, h) / 480.0

    def pt(dx, dy):
        return (int(cx + dx * scale), int(cy + dy * scale))

    head_c = pt(0, -88); head_r = int(22 * scale)
    neck   = pt(0, -62)
    lsho   = pt(-50, -34); rsho = pt(50, -34)
    lelb   = pt(-82,  12); relb = pt(82,  12)
    lwri   = pt(-74,  62); rwri = pt(74,  62)
    lhip   = pt(-30,  52); rhip = pt(30,  52)
    lkne   = pt(-34, 110); rkne = pt(34, 110)
    lank   = pt(-32, 168); rank = pt(32, 168)

    # 暗色肢体线
    lw = max(2, int(2.2 * scale))
    DIM = tuple(int(c * 0.35) for c in accent)

    bones = [
        (neck, lsho), (neck, rsho),
        (lsho, lelb), (lelb, lwri),
        (rsho, relb), (relb, rwri),
        (lsho, lhip), (rsho, rhip), (lhip, rhip),
        (lhip, lkne), (lkne, lank),
        (rhip, rkne), (rkne, rank),
    ]
    for a, b in bones:
        cv2.line(img, a, b, DIM, lw, cv2.LINE_AA)

    # 绘制头部圆形
    cv2.circle(img, head_c, head_r, DIM, lw, cv2.LINE_AA)

    # 关节点
    joints_pts = [neck, lsho, rsho, lelb, relb, lwri, rwri,
                  lhip, rhip, lkne, rkne, lank, rank]
    jr = max(3, int(4 * scale))
    DIM2 = tuple(int(c * 0.55) for c in accent)
    for jp in joints_pts:
        cv2.circle(img, jp, jr + 2, tuple(int(c * 0.15) for c in accent), -1, cv2.LINE_AA)
        cv2.circle(img, jp, jr, DIM2, -1, cv2.LINE_AA)

    # ── 侧边 A/B 徽章 ──────────────────────────────────────────
    badge = f"侧 {side}" if side else ""
    if badge:
        bx, by = 12, 12; bw2, bh2 = 46, 22
        overlay = img.copy()
        cv2.rectangle(overlay, (bx, by), (bx+bw2, by+bh2),
                      tuple(int(c * 0.18) for c in accent), -1)
        cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)
        cv2.rectangle(img, (bx, by), (bx+bw2, by+bh2), accent, 1, cv2.LINE_AA)
        cv2.putText(img, badge, (bx+6, by+15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, accent, 1, cv2.LINE_AA)

    # ── 操作引导文字 ───────────────────────────────────────────
    stopped = "已停止" in text
    line1 = "分析已停止" if stopped else "点击开始分析"
    line2 = "重新开始"   if stopped else "以显示实时动作"

    # 文字底部胶囊背景
    pill_w, pill_h = int(w * 0.52), 46
    pill_x = (w - pill_w) // 2
    pill_y = int(h * 0.72)
    overlay2 = img.copy()
    cv2.rectangle(overlay2, (pill_x, pill_y), (pill_x+pill_w, pill_y+pill_h),
                  (45, 30, 18), -1)
    cv2.addWeighted(overlay2, 0.55, img, 0.45, 0, img)
    cv2.rectangle(img, (pill_x, pill_y), (pill_x+pill_w, pill_y+pill_h),
                  tuple(int(c * 0.45) for c in accent), 1, cv2.LINE_AA)

    (tw1, th1), _ = cv2.getTextSize(line1, cv2.FONT_HERSHEY_SIMPLEX, 0.54, 1)
    cv2.putText(img, line1,
                ((w - tw1)//2, pill_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.54, accent, 1, cv2.LINE_AA)

    (tw2, th2), _ = cv2.getTextSize(line2, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)
    cv2.putText(img, line2,
                ((w - tw2)//2, pill_y + 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                tuple(int(c * 0.65) for c in accent), 1, cv2.LINE_AA)

    # ── 底部渐变高光条 ─────────────────────────────────────────
    bar_h = 3
    for i in range(w):
        t = i / w
        r = int(CYAN[0] + (VIOLET[0] - CYAN[0]) * t) if not is_b else \
            int(VIOLET[0] + (CYAN[0] - VIOLET[0]) * t)
        g = int(CYAN[1] + (VIOLET[1] - CYAN[1]) * t) if not is_b else \
            int(VIOLET[1] + (CYAN[1] - VIOLET[1]) * t)
        b2 = int(CYAN[2] + (VIOLET[2] - CYAN[2]) * t) if not is_b else \
             int(VIOLET[2] + (CYAN[2] - VIOLET[2]) * t)
        cv2.line(img, (i, h-bar_h), (i, h-1), (r, g, b2), 1)

    return img


def draw_skeleton(frame, landmarks, angles, comparison, w, h):
    lm=landmarks
    pts=[(int(lm[i].x*w),int(lm[i].y*h)) for i in range(len(lm))]
    for a,b in POSE_CONNECTIONS:
        if a<len(pts) and b<len(pts):
            cv2.line(frame,pts[a],pts[b],(255,178,56),2,cv2.LINE_AA)
    for pt in pts: cv2.circle(frame,pt,3,(52,211,153),-1)
    for key,info in angles.items():
        b_idx=MP_JOINT_DEF[key][1]; bx,by=pts[b_idx]
        if comparison and key in comparison.get("joints",{}):
            cmp=comparison["joints"][key]; color=GRADE_BGR[cmp["grade"]]
            label=f"{info['cn_name']}:{info['angle']:.0f}({cmp['deviation']:+.0f})"
        else:
            color=(0,200,200); label=f"{info['cn_name']}:{info['angle']:.0f}"
        (tw,th),_=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,0.38,1)
        cv2.rectangle(frame,(bx-2,by-th-4),(bx+tw+2,by+2),(8,12,20),-1)
        cv2.putText(frame,label,(bx,by-2),cv2.FONT_HERSHEY_SIMPLEX,0.38,color,1,cv2.LINE_AA)

# ══════════════════════════════════════════════════════════════
#  SideState — 单侧状态
# ══════════════════════════════════════════════════════════════
class SideState:
    def __init__(self, label:str):
        self.label      = label           # "A" or "B"
        self.source     = "camera"        # 输入源类型：摄像头/视频/C3D
        self.camera_idx = 0
        self.video_path:Optional[str] = None
        self.c3d_loader:Optional[C3DLoader] = None
        self.c3d_name   = ""
        self.c3d_frame  = 0              # 当前播放帧索引
        self.angles:Dict= {}
        self.symmetry:Dict={}
        self.latest_frame:np.ndarray = make_placeholder(text=f"侧 {label} — 等待开始", side=label)
        self.running      = False
        self.detected     = False
        self.fps          = 0.0
        self.data_loaded  = False   # 历史数据是否已装载（独立于 running）
        # 时序历史记录  {"t": 秒, "angles": {关节名:角度}, "lm": [x0,y0,x1,y1,...]}
        from collections import deque
        self.history:deque     = deque(maxlen=1800)
        self.frame_buffer:deque= deque(maxlen=1800)
        self.history_lock  = threading.Lock()
        self._hist_counter = 0

    def to_dict(self)->Dict:
        return {
            "label":       self.label,
            "source":      self.source,
            "running":     self.running,
            "data_loaded": self.data_loaded,
            "n_frames":    len(self.history),
            "detected":    self.detected,
            "fps":         round(self.fps, 1),
            "angles":      self.angles,
            "symmetry":    self.symmetry,
            "c3d_loaded":  self.c3d_loader is not None,
            "c3d_name":    self.c3d_name,
            "c3d_frame":   self.c3d_frame,
            "c3d_total":   self.c3d_loader.n_frames if self.c3d_loader else 0,
        }

# ══════════════════════════════════════════════════════════════
#  SideProcessor — 统一处理线程
# ══════════════════════════════════════════════════════════════
class SideProcessor(threading.Thread):
    def __init__(self, side:SideState, lock:threading.Lock):
        super().__init__(daemon=True)
        self.side=side; self.lock=lock; self._stop=threading.Event()

    def stop(self): self._stop.set()

    def run(self):
        if self.side.source=="c3d":
            self._run_c3d()
        else:
            self._run_video()

    def _run_c3d(self):
        s=self.side; loader=s.c3d_loader
        if not loader: self._finish(); return
        interval=1/30.0; f=0; total=loader.n_frames
        while not self._stop.is_set():
            t0=time.time()
            angles=loader.angles_to_mp_format(f)
            sym=analyze_symmetry(angles)
            frame=loader.render_frame(f,480,360,s.c3d_name[:20] or "C3D")
            with self.lock:
                s.angles=angles; s.symmetry=sym
                s.latest_frame=frame; s.detected=bool(angles)
                s.fps=30.0; s.c3d_frame=f
            # 按约 10fps 采样历史（每 3 帧记录一次）
            s._hist_counter += 1
            if angles and s._hist_counter % 3 == 0:
                norm_ang = angles if not isinstance(list(angles.values())[0], dict)                             else {k: v["angle"] for k, v in angles.items()}
                entry = {"t": round(time.time(), 3), "angles": norm_ang, "lm": []}
                # 渲染 C3D 帧缩略图，供时间轴回放使用
                c3d_thumb = loader.render_frame(f, 320, 240, s.c3d_name[:16] or "C3D")
                ok2, buf2 = cv2.imencode(".jpg", c3d_thumb, [cv2.IMWRITE_JPEG_QUALITY, 65])
                frame_bytes = buf2.tobytes() if ok2 else b""
                with s.history_lock:
                    s.history.append(entry)
                    s.frame_buffer.append(frame_bytes)
            f=(f+1)%total
            elapsed=time.time()-t0
            time.sleep(max(0,interval-elapsed))
        self._finish()

    def _run_video(self):
        s=self.side
        source=s.camera_idx if s.source=="camera" else s.video_path
        cap=cv2.VideoCapture(source)
        if not cap.isOpened(): self._finish(); return
        W=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # 从文件读取原始帧率，摄像头或未知时回退到 30
        native_fps = cap.get(cv2.CAP_PROP_FPS)
        if native_fps <= 0 or native_fps > 240: native_fps = 30.0
        is_video = s.source == "video"
        frame_interval = 1.0 / native_fps if is_video else 0.0

        prev_t = time.time(); display_fps = 0.0
        # ts_ms：严格递增的毫秒计数器，供 MediaPipe VIDEO 模式使用；视频循环时归零
        ts_ms = 0
        total_frame_idx = 0
        # 基于时间的采样：每 HIST_INTERVAL 秒的视频时间记录一条历史，不依赖帧率精度
        HIST_INTERVAL = 0.10   # 历史采样间隔，约 10fps
        _last_hist_video_t = -999.0   # 上一次写入历史记录时的视频时间

        opts=_mp_vision.PoseLandmarkerOptions(
            base_options=_mp_tasks.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=_mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.55,
            min_pose_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        with _mp_vision.PoseLandmarker.create_from_options(opts) as det:
            while not self._stop.is_set():
                t_frame_start = time.time()
                ret, frame = cap.read()
                if not ret:
                    if is_video:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ts_ms = 0            # 重置 MediaPipe 时间戳（视频循环时）
                        _last_hist_video_t = -999.0   # 循环重置，确保新循环立即采样
                        continue
                    break

                # ── 时间戳处理 ──────────────────────────────────────────
                # ts_ms：严格递增计数器，仅供 MediaPipe 使用（不用于历史时间戳）
                ts_ms += max(1, int(1000.0 / native_fps))
                # video_t_sec：视频文件优先用 CAP_PROP_POS_MSEC（文件自带位置，不依赖帧率）；返回 0 时回退帧计数
                if is_video:
                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if pos_msec > 0:
                        video_t_sec = pos_msec / 1000.0
                    else:
                        # 兜底：帧计数/帧率（部分旧编解码器 POS_MSEC 始终返回 0）
                        video_t_sec = total_frame_idx / native_fps
                else:
                    video_t_sec = time.time()
                total_frame_idx += 1

                # ── Pose detection ───────────────────────────────────────
                now = time.time()
                display_fps = 0.9*display_fps + 0.1/(max(now-prev_t, 1e-9)); prev_t=now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                res = det.detect_for_video(mp_img, ts_ms)
                angles = {}; sym = {}; detected = False
                if res.pose_landmarks:
                    detected = True
                    angles = extract_mp_angles(res.pose_landmarks[0], W, H)
                    sym = analyze_symmetry(angles)

                # ── History recording (time-based, 10 fps) ───────────────
                # 当视频时间距上次采样超过 HIST_INTERVAL 时写入历史
                # 使用视频时间（非系统时钟），确保历史覆盖完整视频时长
                if detected and angles and (video_t_sec - _last_hist_video_t) >= HIST_INTERVAL:
                    _last_hist_video_t = video_t_sec
                    lm_flat = []
                    if res.pose_landmarks:
                        for pt in res.pose_landmarks[0]:
                            lm_flat += [round(pt.x, 4), round(pt.y, 4)]
                    entry = {
                        "t":      round(video_t_sec, 3),
                        "angles": {k: v["angle"] for k, v in angles.items()},
                        "lm":     lm_flat,
                    }
                    clean = cv2.resize(frame, (320, 240))
                    ok2, buf2 = cv2.imencode(".jpg", clean, [cv2.IMWRITE_JPEG_QUALITY, 72])
                    frame_bytes = buf2.tobytes() if ok2 else b""
                    with s.history_lock:
                        s.history.append(entry)
                        s.frame_buffer.append(frame_bytes)

                # ── Draw skeleton on live feed ───────────────────────────
                if res.pose_landmarks:
                    draw_skeleton(frame, res.pose_landmarks[0], angles, None, W, H)
                label_fps = display_fps if not is_video else native_fps
                cv2.putText(frame, f"{'Video' if is_video else 'FPS'} {label_fps:.0f}  {s.label}",
                            (8,22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80,180,80), 1, cv2.LINE_AA)
                with self.lock:
                    s.angles=angles; s.symmetry=sym
                    s.latest_frame=frame.copy(); s.detected=detected; s.fps=display_fps

                # ── Throttle to real-time for video files ────────────────
                if is_video:
                    elapsed = time.time() - t_frame_start
                    sleep_t = frame_interval - elapsed
                    if sleep_t > 0:
                        time.sleep(sleep_t)
        cap.release(); self._finish()

    def _finish(self):
        with self.lock:
            self.side.running=False
            self.side.latest_frame=make_placeholder(text=f"侧 {self.side.label} — 已停止", side=self.side.label)

# ══════════════════════════════════════════════════════════════
#  AppState — 全局状态
# ══════════════════════════════════════════════════════════════
class AppState:
    def __init__(self):
        self._lock=threading.Lock()
        self.side_a=SideState("A")
        self.side_b=SideState("B")
        self.comparison:Optional[Dict]=None
        self.last_advice=""
        # AI 服务商设置
        self.api_keys:Dict[str,str]={
            "anthropic": os.environ.get("ANTHROPIC_API_KEY",""),
            "deepseek":  os.environ.get("DEEPSEEK_API_KEY",""),
            "openai":    os.environ.get("OPENAI_API_KEY",""),
            "qwen":      os.environ.get("DASHSCOPE_API_KEY",""),
            "doubao":    os.environ.get("ARK_API_KEY",""),
            "ollama":    "",
        }
        self.provider="anthropic"; self.model=""; self.base_url=""
        self._proc_a:Optional[SideProcessor]=None
        self._proc_b:Optional[SideProcessor]=None

    def snapshot(self)->Dict:
        with self._lock:
            # 基于最新一帧角度的实时对比
            cmp=None
            if self.side_a.angles and self.side_b.angles:
                cmp=compare_sides(self.side_a.angles, self.side_b.angles)
                self.comparison=cmp
            return {
                "side_a":  self.side_a.to_dict(),
                "side_b":  self.side_b.to_dict(),
                "comparison": cmp or self.comparison,
                "last_advice": self.last_advice,
                "provider": self.provider, "model": self.model,
                "api_keys": dict(self.api_keys),
            }

    def start_side(self, which: str):
        with self._lock:
            side = self.side_a if which == "a" else self.side_b
            if side.running: return False, "已在运行"
            if not side.data_loaded: return False, "请先装载数据"
            side.running = True
        # 继续追加到现有历史（不清空）
        side._hist_counter = 0
        proc = SideProcessor(side, self._lock)
        if which == "a": self._proc_a = proc
        else:            self._proc_b = proc
        proc.start(); return True, ""

    def load_data(self, which: str):
        """装载数据槽：清空历史、标记已装载，准备接收分析数据。"""
        with self._lock:
            side = self.side_a if which == "a" else self.side_b
            if side.running: return False, "分析进行中，请先停止"
        with side.history_lock:
            side.history.clear()
            side.frame_buffer.clear()
        side._hist_counter = 0
        with self._lock:
            side.data_loaded = True
        return True, ""

    def unload_data(self, which: str):
        """卸载数据槽：停止分析（如在运行）并清空历史。"""
        self.stop_side(which)
        side = self.side_a if which == "a" else self.side_b
        with side.history_lock:
            side.history.clear()
            side.frame_buffer.clear()
        with self._lock:
            side.data_loaded = False
        return True, ""

    def stop_side(self, which:str):
        with self._lock:
            proc=self._proc_a if which=="a" else self._proc_b
            side=self.side_a if which=="a" else self.side_b
        if proc: proc.stop(); proc.join(timeout=3)
        with self._lock:
            side.running=False
            side.latest_frame=make_placeholder(text=f"侧 {'A' if which=='a' else 'B'} — 已停止", side='A' if which=='a' else 'B')
        if which=="a": self._proc_a=None
        else:          self._proc_b=None

STATE=AppState()

# ══════════════════════════════════════════════════════════════
#  MJPEG 生成器
# ══════════════════════════════════════════════════════════════
def _gen(side:SideState):
    while True:
        with STATE._lock: frame=side.latest_frame.copy()
        ok,buf=cv2.imencode(".jpg",frame,[cv2.IMWRITE_JPEG_QUALITY,72])
        if ok: yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+buf.tobytes()+b"\r\n"
        time.sleep(1/30)

# ══════════════════════════════════════════════════════════════
#  AI 建议
# ══════════════════════════════════════════════════════════════
PROVIDER_DEFAULTS={
    "anthropic":{"model":"claude-sonnet-4-20250514","base_url":""},
    "deepseek": {"model":"deepseek-chat",           "base_url":"https://api.deepseek.com"},
    "openai":   {"model":"gpt-4o",                  "base_url":""},
    "qwen":     {"model":"qwen-plus",               "base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "doubao":   {"model":"doubao-1-5-pro-32k-250115","base_url":"https://ark.cn-beijing.volces.com/api/v3"},
    "ollama":   {"model":"qwen2.5:7b",              "base_url":"http://localhost:11434/v1"},
}

def build_prompt_ts(ts_result: Dict, hist_a: list, hist_b: list,
                    sym_a: Dict, sym_b: Dict, extra: str = "") -> str:
    """
    基于完整时序对比结果构建 AI 提示词。
    输出含关节名称、时段、角度差的语言描述，如：
      'A的左膝在动作进行约25%–50%阶段平均角度为67°，比参考B的83°偏小16°'
    """
    joints = ts_result.get("joints", {})
    n_a = ts_result.get("n_a", 0)
    n_b = ts_result.get("n_b", 0)
    overall = ts_result.get("overall_score", 0)

    # 从历史时间戳估算录制时长
    def dur(hist):
        if len(hist) < 2: return "未知"
        return f"{hist[-1]['t'] - hist[0]['t']:.1f}秒"

    dur_a = dur(hist_a); dur_b = dur(hist_b)

    lines = [
        "你是专业舞蹈教练兼运动生物力学专家。",
        "以下是两位舞者完整动作过程中各关节角度的时序对比数据。",
        f"侧A（被分析舞者）录制时长约{dur_a}（{n_a}帧），",
        f"侧B（参考舞者）录制时长约{dur_b}（{n_b}帧）。",
        f"综合相似度评分：{overall}/100（满分100，越高越接近）。",
        "",
        "【各关节对比详情】",
    ]

    # 按评分升序，最差关节排在前面
    sorted_joints = sorted(joints.items(), key=lambda x: x[1]["score"])
    for k, j in sorted_joints:
        cn = j["cn_name"]
        r  = j["r"]
        rmsd = j["rmsd"]
        scale = j["scale"]
        sc = j["score"]
        ma = j["mean_a"]; mb = j["mean_b"]
        overall_dir = "偏大" if ma > mb else "偏小"
        lines.append(f"\n▶ {cn}（评分{sc}/100，r={r}，RMSD={rmsd}°）")
        lines.append(f"  A全程均值{ma}° vs B全程均值{mb}°，整体{overall_dir}{abs(round(ma-mb,1))}°")
        if abs(scale - 1.0) > 0.1:
            lines.append(f"  [注] A的动作速度约为B的{round(1/scale,2)}×（{'较快' if scale<1 else '较慢'}）")
        # 分段详情，仅输出偏差超过 5° 的时段
        for seg in j.get("segments", []):
            diff = seg["diff"]
            if abs(diff) < 5: continue
            t0 = int(seg["t_start"] * 100); t1 = int(seg["t_end"] * 100)
            lines.append(
                f"  · 动作进行{t0}%–{t1}%阶段：A均值{seg['mean_a']}°，B均值{seg['mean_b']}°，"
                f"A{seg['direction']}{abs(diff)}°"
            )

    # 对称性数据块
    def fmt_sym(d):
        rows = []
        for n, s in d.items():
            sym = "✓对称" if s["symmetric"] else f"✗不对称(差{s['diff']}°)"
            rows.append(f"  {n}: 左{s['left']}°/右{s['right']}° {sym}")
        return "\n".join(rows) if rows else "  暂无数据"

    lines += ["", "【侧A 左右对称性】", fmt_sym(sym_a),
              "", "【侧B 左右对称性】", fmt_sym(sym_b)]

    if extra:
        lines += ["", f"【补充说明】{extra}"]

    lines += [
        "",
        "请用中文并关闭markdown格式，按以下结构给出专业分析（不超过550字）：",
        "1. 整体动作相似度：结合评分和对齐情况简述两人动作的整体吻合程度",
        "2. 主要差异时段（2-3个关节）：针对上方数据，",
        "   明确指出'在某动作阶段，A的某关节比B偏大/偏小X度'，",
        "   说明这一差异对舞蹈表现（爆发力/柔韧性/协调性）的具体影响",
        "3. 速度/节奏差异（如有）：如系统检测到两人速度比差异明显，给出节奏建议",
        "4. 针对性训练建议（2-3条）：根据最差关节的时段差异给出可操作的练习方法",
        "5. 安全提示：偏差>30°的关节请用 ⚠ 标注潜在受伤风险",
        "",
        "语气专业、鼓励，分析需引用具体时段和角度数字，不得泛泛而谈。",
    ]
    return "\n".join(lines)


def call_ai(ts_result: Dict, hist_a: list, hist_b: list,
            sym_a: Dict, sym_b: Dict, extra: str = "") -> str:
    provider = STATE.provider; key = STATE.api_keys.get(provider, "")
    model = STATE.model; base_url = STATE.base_url
    prompt = build_prompt_ts(ts_result, hist_a, hist_b, sym_a, sym_b, extra)
    if not key and provider!="ollama": return f"⚠ 请在「AI 设置」中填入 {provider} 的 API Key"
    if provider=="anthropic":
        if not HAS_ANTHROPIC: return "❌ pip install anthropic"
        try:
            c=_anthropic_mod.Anthropic(api_key=key)
            m=c.messages.create(model=model or PROVIDER_DEFAULTS["anthropic"]["model"],
                                max_tokens=1400,messages=[{"role":"user","content":prompt}])
            return m.content[0].text
        except Exception as e: return f"❌ Anthropic: {e}"
    if provider in ("deepseek","openai","qwen","doubao","ollama"):
        if not HAS_OPENAI: return "❌ pip install openai"
        try:
            defs=PROVIDER_DEFAULTS.get(provider,{})
            url=base_url or defs.get("base_url") or None
            mdl=model or defs.get("model","gpt-4o")
            kw={"api_key":key if key else "ollama"}
            if url: kw["base_url"]=url
            c=_openai_mod.OpenAI(**kw)
            r=c.chat.completions.create(model=mdl,max_tokens=1400,
                                        messages=[{"role":"user","content":prompt}])
            return r.choices[0].message.content
        except Exception as e: return f"❌ {provider}: {e}"
    return f"❌ 未知提供商: {provider}"

# ══════════════════════════════════════════════════════════════
#  Flask 路由
# ══════════════════════════════════════════════════════════════
_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_HERE, 'templates'),
            static_folder=os.path.join(_HERE, 'static'))
app.config["MAX_CONTENT_LENGTH"]=512*1024*1024

@app.route("/")
def index():
    from flask import render_template
    return render_template('index.html',
        has_ezc3d=HAS_EZC3D,
        api_keys_json=json.dumps(STATE.api_keys),
        provider=STATE.provider)

@app.route("/feed_a")
def feed_a(): return Response(_gen(STATE.side_a),mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/feed_b")
def feed_b(): return Response(_gen(STATE.side_b),mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/status")
def api_status(): return jsonify(STATE.snapshot())

@app.route("/api/load_data", methods=["POST"])
def api_load_data():
    which = (request.json or {}).get("which", "a")
    ok, msg = STATE.load_data(which)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/unload_data", methods=["POST"])
def api_unload_data():
    which = (request.json or {}).get("which", "a")
    ok, msg = STATE.unload_data(which)
    return jsonify({"ok": ok, "msg": msg})

@app.route("/api/start", methods=["POST"])
def api_start():
    which=(request.json or {}).get("which","a")
    ok,msg=STATE.start_side(which)
    return jsonify({"ok":ok,"msg":msg})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    which=(request.json or {}).get("which","a")
    STATE.stop_side(which); return jsonify({"ok":True})

@app.route("/api/set_source", methods=["POST"])
def api_set_source():
    d=request.json or {}; which=d.get("which","a")
    side=STATE.side_a if which=="a" else STATE.side_b
    with STATE._lock:
        side.source=d.get("source","camera")
        side.camera_idx=int(d.get("camera_idx",0))
    return jsonify({"ok":True})

@app.route("/api/upload_video", methods=["POST"])
def api_upload_video():
    which=request.form.get("which","a")
    if "file" not in request.files: return jsonify({"ok":False,"msg":"无文件"})
    f=request.files["file"]; ext=Path(f.filename).suffix.lower()
    if ext not in [".mp4",".avi",".mov",".mkv",".webm"]: return jsonify({"ok":False,"msg":"格式不支持"})
    tmp=tempfile.NamedTemporaryFile(suffix=ext,delete=False); f.save(tmp.name); tmp.close()
    side=STATE.side_a if which=="a" else STATE.side_b
    cap=cv2.VideoCapture(tmp.name)
    n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps=cap.get(cv2.CAP_PROP_FPS); cap.release()
    with STATE._lock:
        side.video_path=tmp.name; side.source="video"
    return jsonify({"ok":True,"filename":f.filename,"n_frames":n,"fps":round(fps,1)})

@app.route("/api/upload_c3d", methods=["POST"])
def api_upload_c3d():
    if not HAS_EZC3D: return jsonify({"ok":False,"msg":"请先安装 ezc3d"})
    which=request.form.get("which","a")
    if "file" not in request.files: return jsonify({"ok":False,"msg":"无文件"})
    f=request.files["file"]
    if not f.filename.lower().endswith(".c3d"): return jsonify({"ok":False,"msg":"需要 .c3d 文件"})
    preset=request.form.get("preset","vicon_pig")
    custom=request.form.get("custom_map","").strip()
    try:
        marker_map=json.loads(custom) if custom else PRESET_MAPS.get(preset,DEFAULT_C3D_MAP)
        tmp=tempfile.NamedTemporaryFile(suffix=".c3d",delete=False); f.save(tmp.name); tmp.close()
        loader=C3DLoader(tmp.name,marker_map)
        side=STATE.side_a if which=="a" else STATE.side_b
        with STATE._lock:
            side.c3d_loader=loader; side.c3d_name=f.filename; side.source="c3d"; side.c3d_frame=0
        return jsonify({"ok":True,"filename":f.filename,"n_frames":loader.n_frames,
                        "fps":loader.fps,"loaded_joints":loader.loaded_joints,
                        "missing_joints":loader.missing_joints,"which":which})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route("/api/clear_c3d", methods=["POST"])
def api_clear_c3d():
    which=(request.json or {}).get("which","a")
    side=STATE.side_a if which=="a" else STATE.side_b
    with STATE._lock: side.c3d_loader=None; side.c3d_name=""; side.source="camera"
    return jsonify({"ok":True})

@app.route("/api/set_apikey", methods=["POST"])
def api_set_apikey():
    d=request.json or {}
    with STATE._lock: STATE.api_keys[d.get("provider","anthropic")]=d.get("api_key","").strip()
    return jsonify({"ok":True})

@app.route("/api/set_provider", methods=["POST"])
def api_set_provider():
    d=request.json or {}
    with STATE._lock:
        STATE.provider=d.get("provider","anthropic")
        STATE.model=d.get("model","").strip()
        STATE.base_url=d.get("base_url","").strip()
    return jsonify({"ok":True})

@app.route("/api/advice", methods=["POST"])
def api_advice():
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
        if not hist: return hist
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
    import subprocess
    try:
        r=subprocess.run([sys.executable,"-m","pip","install","ezc3d","--quiet"],
                         capture_output=True,text=True,timeout=120)
        if r.returncode==0: return jsonify({"ok":True,"msg":"安装成功，请重启程序"})
        return jsonify({"ok":False,"msg":r.stderr[-300:]})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route("/api/history")
def api_history():
    which = request.args.get("which", "a")
    limit = min(int(request.args.get("limit", 600)), 1800)
    side  = STATE.side_a if which == "a" else STATE.side_b
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
    return jsonify({"ok": True, "which": which, "data": data,
                    "has_frames": has_frames,
                    "joint_keys": list(MP_JOINT_DEF.keys())})

@app.route("/api/compare_ts")
def api_compare_ts():
    """基于完整时序的双侧对比端点，返回 DTW 对齐评分"""
    with STATE.side_a.history_lock:
        hist_a = list(STATE.side_a.history)
    with STATE.side_b.history_lock:
        hist_b = list(STATE.side_b.history)
    # 将时间戳归一化为相对秒数 (same as /api/history)
    def normalise(hist):
        if not hist: return hist
        t0 = hist[0]["t"]
        return [{**h, "t": round(h["t"] - t0, 3)} for h in hist]
    result = compare_timeseries(normalise(hist_a), normalise(hist_b))
    return jsonify(result)

@app.route("/api/aligned_series")
def api_aligned_series():
    """返回各关节对齐后的角度序列及对应的骨架帧坐标。"""
    with STATE.side_a.history_lock:
        hist_a = list(STATE.side_a.history)
    with STATE.side_b.history_lock:
        hist_b = list(STATE.side_b.history)

    def rel(h):
        if not h: return h
        t0 = h[0]["t"]
        return [{**x, "t": round(x["t"]-t0, 3)} for x in h]
    hist_a = rel(hist_a); hist_b = rel(hist_b)

    MIN = 15
    if len(hist_a) < MIN or len(hist_b) < MIN:
        return jsonify({"ok": False,
                        "reason": f"需要至少{MIN}帧（A:{len(hist_a)} B:{len(hist_b)}）"})

    N_PTS = 200
    joint_keys = list(MP_JOINT_DEF.keys())
    aligned_joints = {}
    # 各关节独立对齐用于评分；全局骨架对齐由下方 _composite_global_align 完成

    for k in joint_keys:
        va = np.array([h["angles"].get(k, np.nan) for h in hist_a], dtype=float)
        vb = np.array([h["angles"].get(k, np.nan) for h in hist_b], dtype=float)
        fa = _fill_nan(va); fb = _fill_nan(vb)
        if fa is None or fb is None: continue
        aln = _best_align_joint(fa, fb, n_pts=N_PTS)
        aligned_joints[k] = {
            "cn_name": MP_JOINT_DEF[k][3],
            "a":       [round(float(v),1) for v in aln["a_aligned"]],
            "b":       [round(float(v),1) for v in aln["b_aligned"]],
        }
        # 各关节对齐参数已写入 aligned_joints，供前端展示

    if not aligned_joints:
        return jsonify({"ok": False, "reason": "无共同可用关节"})

    # ── 两阶段全局对齐：滑窗找起始点 → DTW 路径 ─────────────────
    # frame_a[k] / frame_b[k] 是 hist_a/hist_b 的原始帧索引
    # 每对 (frame_a[k], frame_b[k]) 对应动作的"同一时刻"（DTW 规整）
    g_aln  = _composite_global_align(hist_a, hist_b, n_pts=N_PTS)
    frame_a_idx = g_aln["frame_a"]   # list of int, 长度 N_PTS
    frame_b_idx = g_aln["frame_b"]   # list of int, 长度 N_PTS
    n_a, n_b    = len(hist_a), len(hist_b)

    lm_a = [hist_a[min(ia, n_a-1)].get("lm", []) for ia in frame_a_idx]
    lm_b = [hist_b[min(ib, n_b-1)].get("lm", []) for ib in frame_b_idx]

    # 录制时长信息
    dur_a = round(hist_a[-1]["t"] - hist_a[0]["t"], 2) if len(hist_a)>1 else 0
    dur_b = round(hist_b[-1]["t"] - hist_b[0]["t"], 2) if len(hist_b)>1 else 0

    return jsonify({
        "ok":            True,
        "n_pts":         N_PTS,
        "joints":        aligned_joints,
        "global_a_off":  g_aln["a_off"],
        "global_b_off":  g_aln["b_off"],
        "global_r":      round(g_aln.get("r", 0.0), 3) if "r" in g_aln else 0,
        "lm_a":          lm_a,
        "lm_b":          lm_b,
        "dur_a":         dur_a,
        "dur_b":         dur_b,
        "n_a":           n_a,
        "n_b":           n_b,
    })

@app.route("/api/frame")
def api_frame():
    which = request.args.get("which", "a")
    idx   = int(request.args.get("idx", 0))
    side  = STATE.side_a if which == "a" else STATE.side_b
    with side.history_lock:
        buf_list = list(side.frame_buffer)
    if not buf_list or idx < 0 or idx >= len(buf_list):
        return Response(b"", mimetype="image/jpeg", status=204)
    frame_bytes = buf_list[idx]
    if not frame_bytes:
        return Response(b"", mimetype="image/jpeg", status=204)
    return Response(frame_bytes, mimetype="image/jpeg",
                    headers={"Cache-Control": "no-cache"})

@app.route("/api/clear_history", methods=["POST"])
def api_clear_history():
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
    snap=STATE.snapshot()
    snap["generated_at"]=datetime.now().isoformat()
    buf=io.BytesIO(json.dumps(snap,ensure_ascii=False,indent=2).encode())
    buf.seek(0)
    return send_file(buf,as_attachment=True,
                     download_name=f"dance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                     mimetype="application/json")

# ══════════════════════════════════════════════════════════════
#  HTML 模板
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  启动入口
# ══════════════════════════════════════════════════════════════
def open_browser():
    time.sleep(2); webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("""
+================================================+
|   舞蹈动作分析系统 v3.0                         |
|   浏览器将在 2 秒后自动打开                     |
|   手动访问: http://127.0.0.1:5000              |
|   按 Ctrl+C 停止                               |
+================================================+""")
    missing=[]
    if not HAS_ANTHROPIC: missing.append("anthropic")
    if not HAS_OPENAI:    missing.append("openai")
    if not HAS_EZC3D:     missing.append("ezc3d")
    if missing: print(f"[WARN] 可选功能缺失，可运行: pip install {' '.join(missing)}")
    ensure_model()
    threading.Thread(target=open_browser,daemon=True).start()
    app.run(host="127.0.0.1",port=5000,debug=False,threaded=True)
