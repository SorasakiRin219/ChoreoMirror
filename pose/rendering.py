"""
骨架绘制模块,
骨架绘制、占位图生成和中文文字渲染函数
"""
from typing import Dict, Optional
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

from config.constants import POSE_CONNECTIONS, MP_JOINT_DEF


# 评分颜色映射
GRADE_BGR = {
    "excellent": (0, 210, 80),
    "good": (0, 200, 200),
    "warning": (0, 165, 255),
    "poor": (30, 30, 220)
}


def make_placeholder(w: int = 480, h: int = 360, text: str = "等待开始...", side: str = "") -> np.ndarray:
    """
    深海军蓝+紫色占位画布
    A 侧天蓝色，B 侧紫色

    Args:
        w: 图像宽度
        h: 图像高度
        text: 提示文本
        side: 侧标识（"A" 或 "B"）

    Returns:
        占位图像（BGR 格式）
    """
    is_b = (str(side).upper() == "B")

    # BGR 颜色元组
    CYAN = (255, 178, 56)      # #38b2ff
    VIOLET = (250, 139, 167)   # #a78bfa
    accent = VIOLET if is_b else CYAN

    BG_DEEP = (26, 14, 8)      # #080e1a
    BG_CARD = (53, 22, 13)     # #0d1626
    GRID_CLR = (64, 46, 23)

    img = np.full((h, w, 3), BG_DEEP, np.uint8)

    # 点阵网格背景
    for x in range(0, w, 28):
        for y in range(0, h, 28):
            cv2.circle(img, (x, y), 1, GRID_CLR, -1, cv2.LINE_AA)

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

    # 骨架轮廓
    scale = min(w, h) / 480.0

    def pt(dx, dy):
        return (int(cx + dx * scale), int(cy + dy * scale))

    head_c = pt(0, -88)
    head_r = int(22 * scale)
    neck = pt(0, -62)
    lsho = pt(-50, -34)
    rsho = pt(50, -34)
    lelb = pt(-82, 12)
    relb = pt(82, 12)
    lwri = pt(-74, 62)
    rwri = pt(74, 62)
    lhip = pt(-30, 52)
    rhip = pt(30, 52)
    lkne = pt(-34, 110)
    rkne = pt(34, 110)
    lank = pt(-32, 168)
    rank = pt(32, 168)

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

    cv2.circle(img, head_c, head_r, DIM, lw, cv2.LINE_AA)

    # 关节点
    joints_pts = [neck, lsho, rsho, lelb, relb, lwri, rwri,
                  lhip, rhip, lkne, rkne, lank, rank]
    jr = max(3, int(4 * scale))
    DIM2 = tuple(int(c * 0.55) for c in accent)
    for jp in joints_pts:
        cv2.circle(img, jp, jr + 2, tuple(int(c * 0.15) for c in accent), -1, cv2.LINE_AA)
        cv2.circle(img, jp, jr, DIM2, -1, cv2.LINE_AA)

    # PIL 绘制中文文字（OpenCV不支持中文，使用 PIL 绘制后再转换回 OpenCV 格式）
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # 字体加载策略（跨平台兼容）
    font = None
    font_paths = [
        # Windows 系统字体
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        # macOS 系统字体
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux 系统字体
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, 18)
            break
        except:
            continue

    if font is None:
        font = ImageFont.load_default()

    # 文字内容准备
    stopped = "已停止" in text or "stopped" in text.lower()

    # 主标题（侧 A / 侧 B 徽章文字）
    badge_text = f"侧 {side}" if side else ""

    # 中央操作提示（两行）
    if stopped:
        main_line = "分析已停止"
        sub_line = "点击重新开始"
    else:
        main_line = "点击开始分析"
        sub_line = "以显示实时动作"

    # 绘制徽章文字（左上角）
    if badge_text:
        bx, by = 12, 12
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        padding = 6

        # 绘制半透明背景胶囊
        overlay = Image.new('RGBA', pil_img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [bx, by, bx + text_w + padding*2, by + text_h + padding*2],
            radius=4,
            fill=(int(accent[0]*0.2), int(accent[1]*0.2), int(accent[2]*0.2), 180)
        )
        pil_img = Image.alpha_composite(pil_img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(pil_img)

        # 绘制文字（使用 RGB 元组，注意 PIL 使用 RGB 而非 BGR）
        pil_accent = (accent[2], accent[1], accent[0])  # BGR -> RGB 转换
        draw.text((bx + padding, by + padding//2), badge_text, font=font, fill=pil_accent)

    # 绘制中央提示文字（底部胶囊区域）
    bbox_main = draw.textbbox((0, 0), main_line, font=font)
    bbox_sub = draw.textbbox((0, 0), sub_line, font=font)
    max_w = max(bbox_main[2], bbox_sub[2])
    total_h = (bbox_main[3] - bbox_main[1]) + (bbox_sub[3] - bbox_sub[1]) + 8

    pill_w = int(max_w * 1.2)
    pill_h = int(total_h * 1.5)
    pill_x = (w - pill_w) // 2
    pill_y = int(h * 0.72)

    # 绘制胶囊背景（带透明度）
    overlay = Image.new('RGBA', pil_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
        radius=12,
        fill=(45, 30, 18, 200),
        outline=(int(accent[2]*0.6), int(accent[1]*0.6), int(accent[0]*0.6), 255),
        width=1
    )
    pil_img = Image.alpha_composite(pil_img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(pil_img)

    # 绘制主文字（白色）
    main_x = (w - (bbox_main[2] - bbox_main[0])) // 2
    main_y = pill_y + 10
    draw.text((main_x, main_y), main_line, font=font, fill=(255, 255, 255))

    # 绘制副文字（半透明强调色）
    sub_color = (int(accent[2]*0.8), int(accent[1]*0.8), int(accent[0]*0.8))
    sub_x = (w - (bbox_sub[2] - bbox_sub[0])) // 2
    sub_y = main_y + (bbox_main[3] - bbox_main[1]) + 6
    draw.text((sub_x, sub_y), sub_line, font=font, fill=sub_color)

    # 底部渐变高光条
    bar_h = 3
    for i in range(w):
        t = i / w
        r = int(CYAN[2] + (VIOLET[2] - CYAN[2]) * t) if not is_b else int(VIOLET[2] + (CYAN[2] - VIOLET[2]) * t)
        g = int(CYAN[1] + (VIOLET[1] - CYAN[1]) * t) if not is_b else int(VIOLET[1] + (CYAN[1] - VIOLET[1]) * t)
        b = int(CYAN[0] + (VIOLET[0] - CYAN[0]) * t) if not is_b else int(VIOLET[0] + (CYAN[0] - VIOLET[0]) * t)
        cv2.line(img, (i, h-bar_h), (i, h-1), (b, g, r), 1)  # RGB -> BGR 转换

    # 将 PIL 图像转回 OpenCV 格式
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return img


def draw_skeleton(frame: np.ndarray, landmarks, angles: Dict, comparison: Optional[Dict], w: int, h: int) -> None:
    """
    绘制骨架和关节角度中文显示
    Args:
        frame: 要绘制的图像帧（会原地修改）
        landmarks: MediaPipe 姿态关键点
        angles: 关节角度字典
        comparison: 对比结果字典（可选）
        w: 图像宽度
        h: 图像高度
    """
    lm = landmarks
    pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in range(len(lm))]

    # 骨架连接线
    for a, b in POSE_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            cv2.line(frame, pts[a], pts[b], (56, 189, 248), 2, cv2.LINE_AA)  # 青色 #38bdf8

    # 关节点
    for pt in pts:
        cv2.circle(frame, pt, 4, (74, 222, 128), -1)  # 绿色关节点

    # 用 PIL 绘制中文文本
    try:
        # OpenCV 图像转换为 PIL 图像
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # 字体加载
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",  # macOS
            "/System/Library/Fonts/STHeiti Light.ttc",  # macOS 备选
            "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
            "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux 备选
        ]
        font = None
        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, 16)
                break
            except:
                continue
        if font is None:
            font = ImageFont.load_default()

        for key, info in angles.items():
            b_idx = MP_JOINT_DEF[key][1]
            bx, by = pts[b_idx]

            if comparison and key in comparison.get("joints", {}):
                cmp = comparison["joints"][key]
                label = f"{info['cn_name']}: {info['angle']:.0f} ({cmp['deviation']:+.0f})"
                color = GRADE_BGR[cmp['grade']]
            else:
                label = f"{info['cn_name']}: {info['angle']:.0f}"
                color = (56, 189, 248)

            # 计算文本尺寸
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            # 背景框
            bg_x1 = max(0, bx - 2)
            bg_y1 = max(0, by - text_h - 6)
            bg_x2 = min(w, bx + text_w + 4)
            bg_y2 = min(h, by)

            draw.rectangle(
                [bg_x1, bg_y1, bg_x2, bg_y2],
                fill=(11, 17, 32, 200),
                outline=tuple(color) + (255,)
            )

            draw.text((bx, by - text_h - 3), label, font=font, fill=color)

        # 转换回 OpenCV 格式
        frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    except ImportError:
        # 如果没有 PIL 就用 OpenCV 绘制英文标签
        for key, info in angles.items():
            b_idx = MP_JOINT_DEF[key][1]
            bx, by = pts[b_idx]
            label = f"{key}: {info['angle']:.0f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            cv2.rectangle(frame, (bx-2, by-th-4), (bx+tw+2, by+2), (8, 12, 20), -1)
            cv2.putText(frame, label, (bx, by-2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 200), 1, cv2.LINE_AA)
    except Exception:
        pass
