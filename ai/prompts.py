"""
AI 提示词模块

包含构建 AI 分析提示词的函数。
"""


def build_prompt_ts(ts_result: dict, hist_a: list, hist_b: list,
                    sym_a: dict, sym_b: dict, extra: str = "") -> str:
    """
    基于完整时序对比结果构建 AI 提示词。
    输出含关节名称、时段、角度差的语言描述，如：
      'A的左膝在动作进行约25%–50%阶段平均角度为67°，比参考B的83°偏小16°'

    Args:
        ts_result: 时序对比结果
        hist_a: 侧 A 历史数据
        hist_b: 侧 B 历史数据
        sym_a: 侧 A 对称性分析
        sym_b: 侧 B 对称性分析
        extra: 补充说明

    Returns:
        AI 提示词字符串
    """
    joints = ts_result.get("joints", {})
    n_a = ts_result.get("n_a", 0)
    n_b = ts_result.get("n_b", 0)
    overall = ts_result.get("overall_score", 0)

    # 从历史时间戳估算录制时长
    def dur(hist):
        if len(hist) < 2:
            return "未知"
        return f"{hist[-1]['t'] - hist[0]['t']:.1f}秒"

    dur_a = dur(hist_a)
    dur_b = dur(hist_b)

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
        r = j["r"]
        rmsd = j["rmsd"]
        scale = j["scale"]
        sc = j["score"]
        ma = j["mean_a"]
        mb = j["mean_b"]
        overall_dir = "偏大" if ma > mb else "偏小"

        lines.append(f"\n▶ {cn}（评分{sc}/100，r={r}，RMSD={rmsd}°）")
        lines.append(f"  A全程均值{ma}° vs B全程均值{mb}°，整体{overall_dir}{abs(round(ma-mb, 1))}°")

        if abs(scale - 1.0) > 0.1:
            lines.append(f"  [注] A的动作速度约为B的{round(1/scale, 2)}×（{'较快' if scale < 1 else '较慢'}）")

        # 分段详情，仅输出偏差超过 5° 的时段
        for seg in j.get("segments", []):
            diff = seg["diff"]
            if abs(diff) < 5:
                continue
            t0 = int(seg["t_start"] * 100)
            t1 = int(seg["t_end"] * 100)
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

    lines += [
        "", "【侧A 左右对称性】", fmt_sym(sym_a),
        "", "【侧B 左右对称性】", fmt_sym(sym_b)
    ]

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
