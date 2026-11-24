"""부품 하나(솔리드) → 여러 방향 이미지.  render_dataset.py · predict_bom.py 가 함께 쓴다.

- STEP 조립품을 솔리드(부품) 단위로 나눈다      → split_solids()   (기존 day1/step_inspect.py 재활용)
- 부품마다 크기를 1로 맞춰(모양만 보게) 여러 각도로 렌더 → render_views()
- AI HUB 데이터가 아직 없을 때 쓸 연습용 가짜 부품   → demo_part()
"""
import os
import sys

import numpy as np

CODE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
sys.path.insert(0, os.path.join(CODE, "day1"))

# 카메라 위치 (고도, 방위각) — 부품 1개당 이 개수만큼 이미지가 나온다
VIEWS = [(20, -60), (20, 30), (20, 120), (20, 210), (60, -45), (-20, 45)]


# ---------------------------------------------------------------- STEP → 솔리드
def split_solids(step_path, deflection=2.0):
    """STEP 을 읽어 솔리드(부품)마다 (삼각형 배열, 외곽 크기[mm]) 를 돌려준다. OCP 필요 (AWS 서버)."""
    from step_inspect import load_step, triangles          # 기존 교재 코드 그대로 사용
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    shape = load_step(step_path)
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    parts = []
    while exp.More():
        tris = triangles(exp.Current(), deflection)
        if len(tris):
            pts = tris.reshape(-1, 3)
            parts.append((tris, (pts.max(0) - pts.min(0)).round(1).tolist()))
        exp.Next()
    return parts


# ---------------------------------------------------------------- 렌더링
def normalize(tris):
    """가운데로 옮기고 가장 긴 변을 1 로 — AI 가 '크기'가 아니라 '모양'을 보게 한다."""
    pts = tris.reshape(-1, 3)
    lo, hi = pts.min(0), pts.max(0)
    return (tris - (lo + hi) / 2) / max((hi - lo).max(), 1e-9)


def render_views(tris, out_prefix, size=128, max_tris=20000):
    """VIEWS 각도마다 회색조 PNG 를 저장하고 파일 경로 목록을 돌려준다 (CPU · matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tris = normalize(np.asarray(tris, dtype=float))
    if len(tris) > max_tris:
        tris = tris[np.linspace(0, len(tris) - 1, max_tris).astype(int)]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    paths = []
    for k, (elev, azim) in enumerate(VIEWS):
        fig = plt.figure(figsize=(size / 64, size / 64), dpi=64)
        ax = fig.add_axes([0, 0, 1, 1], projection="3d")
        e, a = np.radians(elev), np.radians(azim)
        light = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        g = 0.25 + 0.7 * np.abs(n @ light)
        ax.add_collection3d(Poly3DCollection(tris, facecolors=np.c_[g, g, g, np.ones_like(g)], linewidths=0))
        ax.set_xlim(-0.55, 0.55); ax.set_ylim(-0.55, 0.55); ax.set_zlim(-0.55, 0.55)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        p = f"{out_prefix}_v{k}.png"
        fig.savefig(p, facecolor="white")
        plt.close(fig)
        paths.append(p)
    return paths


# ---------------------------------------------------------------- 연습용 가짜 부품
def _box(w, d, h, x=0.0, y=0.0, z=0.0):
    v = np.array([[x, y, z], [x + w, y, z], [x + w, y + d, z], [x, y + d, z],
                  [x, y, z + h], [x + w, y, z + h], [x + w, y + d, z + h], [x, y + d, z + h]])
    f = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v[np.array(f)]


def _cylinder(r, h, seg=24, z=0.0):
    t = np.linspace(0, 2 * np.pi, seg + 1)
    tris = []
    for a, b in zip(t[:-1], t[1:]):
        p1, p2 = [r * np.cos(a), r * np.sin(a)], [r * np.cos(b), r * np.sin(b)]
        tris += [[[*p1, z], [*p2, z], [*p2, z + h]], [[*p1, z], [*p2, z + h], [*p1, z + h]],
                 [[0, 0, z], [*p2, z], [*p1, z]], [[0, 0, z + h], [*p1, z + h], [*p2, z + h]]]
    return np.array(tris)


DEMO_CLASSES = ["bolt", "bracket", "plate", "profile"]


def demo_part(label, rng):
    """연습용 가짜 부품 메쉬. 실제 프로젝트에서는 AI HUB STEP 으로 바꾼다."""
    s = rng.uniform(0.7, 1.3, 3)
    if label == "bolt":           # 머리 + 긴 몸통
        return np.concatenate([_cylinder(8 * s[0], 6 * s[1]), _cylinder(4 * s[0], 40 * s[2], z=6 * s[1])])
    if label == "bracket":        # ㄱ자 꺾쇠
        t = 4 * s[2]
        return np.concatenate([_box(40 * s[0], 30 * s[1], t), _box(t, 30 * s[1], 40 * s[0])])
    if label == "plate":          # 얇은 판
        return _box(100 * s[0], 70 * s[1], 3 * s[2])
    if label == "profile":        # 3030 프로파일처럼 긴 각재 + 홈
        L = 300 * s[2]
        return np.concatenate([_box(30, 30, L), _box(8, 2, L, 11, -2), _box(8, 2, L, 11, 30)])
    raise ValueError(label)
