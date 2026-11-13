"""CATIA 없이 형상을 미리 보는 간단한 3D 그림 (matplotlib).

GUI의 '미리보기' 창과 수업 자료 이미지에 함께 쓴다.
상자 목록 boxes = [(x, y, z, dx, dy, dz, (r,g,b)), ...]  (색은 0~1)
"""
import numpy as np
import matplotlib
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# 한글 제목용 글꼴 (Windows: 맑은 고딕, 리눅스: 나눔/Noto)
from matplotlib import font_manager as _fm
_have = {f.name for f in _fm.fontManager.ttflist}
matplotlib.rcParams["font.family"] = [f for f in ("Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans CJK JP")
                                      if f in _have] + ["DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def _faces(x, y, z, dx, dy, dz):
    p = np.array([[x, y, z], [x + dx, y, z], [x + dx, y + dy, z], [x, y + dy, z],
                  [x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]])
    idx = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [0, 3, 7, 4]]
    return [p[i] for i in idx]


def draw_boxes(ax, boxes, view="iso", alpha=1.0):
    faces, colors = [], []
    shade = [0.75, 1.0, 0.85, 0.7, 0.95, 0.8]       # 면마다 밝기를 조금씩 달리해 입체감
    for (x, y, z, dx, dy, dz, c) in boxes:
        for f, s in zip(_faces(x, y, z, dx, dy, dz), shade):
            faces.append(f)
            colors.append((c[0] * s, c[1] * s, c[2] * s, c[3] if len(c) > 3 else alpha))
    ax.add_collection3d(Poly3DCollection(faces, facecolors=colors, edgecolors=(0.2, 0.2, 0.25, 0.35), linewidths=0.3))
    pts = np.array([[b[0], b[1], b[2]] for b in boxes] + [[b[0] + b[3], b[1] + b[4], b[2] + b[5]] for b in boxes])
    lo, hi = pts.min(0), pts.max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2 * 1.05
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    angles = {"iso": (22, -60), "front": (0, -90), "top": (90, -90), "side": (0, 0)}
    ax.view_init(*angles.get(view, angles["iso"]))
    ax.set_axis_off()


def save_figure(boxes, path, title="", view="iso", size=(6, 5)):
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=size, dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    draw_boxes(ax, boxes, view)
    if title:
        ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
