"""FOUP(웨이퍼 운반 용기) 조립품 자동 생성 (영상: CATIA FOUP 200~450mm).

웨이퍼 지름(200/300/450)과 웨이퍼 개수(0~25)를 넣으면
슬롯 간격·외곽 치수를 계산해서 부품 14종 조립품을 만들고, 치수·규격 검토 보고서를 쓴다.
※ 수업용 단순화 모델입니다. 실제 SEMI 규격 적합 판정용이 아닙니다.

실행:
    python day2/foup.py --size 300 --wafers 25
    python day2/foup.py --all            # 200/300/450 세 가지를 만들고 한 조립품에 나란히 배치
    python day2/foup.py --size 450 --dry-run
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad

# 크기별 기준값 (수업용): 슬롯 간격, 웨이퍼 두께, 벽-웨이퍼 여유
SPEC = {
    200: {"pitch": 6.35, "t": 0.725, "gap": 22.0},
    300: {"pitch": 10.0, "t": 0.775, "gap": 25.0},
    450: {"pitch": 12.0, "t": 0.925, "gap": 30.0},
}
SLOTS = 25
WALL = 4.0                      # 외벽 두께

GRAY = (205, 210, 215); DARK = (60, 64, 72); BLUE = (50, 95, 200); CLEAR = (180, 200, 215)


def dims(size, wafers=SLOTS):
    """외곽 치수와 슬롯 높이 계산."""
    if size not in SPEC:
        raise ValueError("웨이퍼 크기는 200, 300, 450 중 하나")
    if not 0 <= wafers <= SLOTS:
        raise ValueError(f"웨이퍼 개수는 0~{SLOTS}")
    s = SPEC[size]
    inner_w = size + 2 * s["gap"]                       # 좌우: 웨이퍼 + 여유
    inner_d = size + s["gap"] + 15                      # 앞뒤: 앞쪽 리테이너 공간 15
    inner_h = SLOTS * s["pitch"] + 40                   # 위아래: 슬롯 + 여유
    W, D, H = inner_w + 2 * WALL, inner_d + 2 * WALL, inner_h + 2 * WALL
    z0 = WALL + 20                                      # 첫 슬롯 높이
    slot_z = [z0 + i * s["pitch"] for i in range(SLOTS)]
    return {"size": size, "wafers": wafers, "W": W, "D": D, "H": H, "pitch": s["pitch"],
            "t": s["t"], "gap": s["gap"], "slot_z": slot_z}


def parts_layout(g):
    """부품 이름 → 상자 목록 [(x,y,z,dx,dy,dz)], 원기둥 목록 [(cx,cy,z,r,h)], 색.
    좌표: X 좌우, Y 앞(0)→뒤(D), Z 위. 문(도어)은 앞쪽 y<0."""
    W, D, H, t, s = g["W"], g["D"], g["H"], WALL, g["size"]
    cx, cy = W / 2, D / 2 + 5
    L = {}
    L["Shell"] = ([(0, 0, 0, W, D, t), (0, 0, H - t, W, D, t), (0, 0, t, t, D, H - 2 * t),
                   (W - t, 0, t, t, D, H - 2 * t), (0, D - t, t, W, t, H - 2 * t)], [], CLEAR)
    L["Door"] = ([(0, -12, 0, W, 12, H)], [], DARK)
    L["Door_Gasket"] = ([(t, 0, t, W - 2 * t, 1, H - 2 * t)], [], (30, 30, 30))
    L["Latch_Cam_L"] = ([(W * 0.25 - 20, -18, H / 2 - 10, 40, 6, 20)], [], (90, 90, 95))
    L["Latch_Cam_R"] = ([(W * 0.75 - 20, -18, H / 2 - 10, 40, 6, 20)], [], (90, 90, 95))
    L["Front_Retainer"] = ([(cx - s * 0.2, t, t + 10, s * 0.4, 8, H - 2 * t - 20)], [], (120, 120, 130))
    L["Rear_Retainer"] = ([(cx - s * 0.2, D - t - 8, t + 10, s * 0.4, 8, H - 2 * t - 20)], [], (120, 120, 130))
    # 좌우 웨이퍼 지지대: 세로 기둥 + 슬롯마다 받침 이빨
    for side, x in (("L", t), ("R", W - t - 12)):
        boxes = [(x, cy - s * 0.3, t, 12, s * 0.6, H - 2 * t)]
        tooth = g["gap"] - 4                               # 웨이퍼 가장자리 밑으로 약 8mm 들어가는 길이
        tooth_x = x - tooth if side == "R" else x + 12
        boxes += [(tooth_x, cy - s * 0.25, z - 1.2, tooth, s * 0.5, 1.2) for z in g["slot_z"]]
        L[f"Wafer_Support_{side}"] = (boxes, [], (230, 230, 235))
    L["KC_Plate"] = ([(cx - s * 0.35, cy - s * 0.35, -10, s * 0.7, s * 0.7, 10)], [], DARK)
    L["Robotic_Flange"] = ([(cx - s * 0.25, cy - s * 0.25, H + 25, s * 0.5, s * 0.5, 10)],
                           [(cx, cy, H, 30, 25)], DARK)
    L["Side_Handles"] = ([(-20, cy - 60, H * 0.45, 20, 120, 40), (W, cy - 60, H * 0.45, 20, 120, 40)], [], BLUE)
    L["Wafers"] = ([], [(cx, cy, z, s / 2, g["t"]) for z in g["slot_z"][:g["wafers"]]], (150, 170, 200))
    return L


def to_boxes(g, dx=0):
    """미리보기용: 원기둥은 정사각 상자로 근사."""
    out = []
    for name, (boxes, cyls, rgb) in parts_layout(g).items():
        c = tuple(v / 255 for v in rgb)
        if name in ("Shell", "Door", "Door_Gasket"):      # 겉면은 반투명 → 안쪽 웨이퍼가 보이게
            c = c + (0.28,)
        for (x, y, z, a, b, h) in boxes:
            if a > 0 and b > 0 and h > 0:
                out.append((x + dx, y, z, a, b, h, c))
        for (x, y, z, r, h) in cyls:
            out.append((x - r * 0.886 + dx, y - r * 0.886, z, r * 1.772, r * 1.772, max(h, 0.8), c))
    return out


def report(g):
    """치수·규격 검토 보고서 (텍스트). 수업용 판정 기준."""
    lines = [f"# FOUP {g['size']} mm 치수 검토 보고서", "",
             f"- 외곽: {g['W']:.1f} x {g['D']:.1f} x {g['H']:.1f} mm (W x D x H, 도어/핸들 제외)",
             f"- 슬롯: {SLOTS}개, 간격 {g['pitch']} mm, 웨이퍼 두께 {g['t']} mm, 장착 {g['wafers']}장", ""]
    checks = [
        ("슬롯 간격 ≥ 웨이퍼 두께 x 5", g["pitch"] >= g["t"] * 5),
        ("좌우 여유 ≥ 20 mm", g["gap"] >= 20),
        ("맨 위 슬롯 위 여유 ≥ 15 mm", g["H"] - WALL - g["slot_z"][-1] >= 15),
        ("웨이퍼 개수 0~25", 0 <= g["wafers"] <= SLOTS),
    ]
    lines.append("| 항목 | 결과 |")
    lines.append("|---|---|")
    for name, ok in checks:
        lines.append(f"| {name} | {'통과' if ok else '확인 필요'} |")
    lines += ["", "※ 수업용 단순화 모델 — SEMI 규격 적합 판정 미완료"]
    return "\n".join(lines)


def build_one(catia, size, wafers, out_base="output", tag="v3"):
    g = dims(size, wafers)
    name = f"FOUP_Assembly_{tag}_{size}mm"
    print(f"[계산] FOUP {size}mm: 외곽 {g['W']:.0f}x{g['D']:.0f}x{g['H']:.0f}, 슬롯 간격 {g['pitch']}, 웨이퍼 {wafers}장")
    doc, root = cad.new_product(catia, name)
    catia.RefreshDisplay = False
    try:
        for pname, (boxes, cyls, rgb) in parts_layout(g).items():
            if not boxes and not cyls:
                continue
            comp, part = cad.add_part(root, f"FOUP_{pname}_{size}")
            for i, (x, y, z, a, b, h) in enumerate(boxes, 1):
                cad.box(part, x, y, z, a, b, h, name=f"{pname}_{i}")
            for i, (x, y, z, r, h) in enumerate(cyls, 1):
                cad.cylinder(part, x, y, z, r, h, name=f"{pname}_C{i}")
            cad.finish(part)
            cad.set_color(doc, comp, rgb)
    finally:
        catia.RefreshDisplay = True
    root.Update()
    out = cad.make_out_dir(out_base, name)
    prod_path = cad.save_assembly(doc, out)
    cad.capture(catia, os.path.join(out, f"{name}.jpg"))
    with open(os.path.join(out, f"{name}_report.md"), "w", encoding="utf-8") as f:
        f.write(report(g))
    with open(os.path.join(out, f"{name}_params.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in g.items() if k != "slot_z"}, f, ensure_ascii=False, indent=2)
    print(f"[완료] {out}")
    return prod_path


def build_all(catia, wafers=25, out_base="output"):
    """세 크기를 만들고, 새 조립품에 불러와 X 방향으로 나란히 배치."""
    paths = [build_one(catia, s, wafers, out_base) for s in (200, 300, 450)]
    doc, root = cad.new_product(catia, "FOUP_SET_200_300_450")
    root.Products.AddComponentsFromFiles(paths, "All")
    x = 0.0
    for i, s in enumerate((200, 300, 450), 1):
        comp = root.Products.Item(i)
        comp.Move.Apply([1, 0, 0, 0, 1, 0, 0, 0, 1, x, 0, 0])     # 회전 없음 + X로 x만큼 이동
        x += dims(s)["W"] + 150
    root.Update()
    out = cad.make_out_dir(out_base, "FOUP_SET")
    doc.SaveAs(os.path.join(out, "FOUP_SET_200_300_450.CATProduct"))
    cad.capture(catia, os.path.join(out, "FOUP_SET.jpg"))
    print(f"[완료] 3종 배치 조립품: {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=300, choices=[200, 300, 450])
    ap.add_argument("--wafers", type=int, default=25)
    ap.add_argument("--all", action="store_true", help="200/300/450 모두 생성 후 나란히 배치")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    catia = get_catia(dry_run=a.dry_run)
    if a.all:
        build_all(catia, a.wafers, a.out)
    else:
        build_one(catia, a.size, a.wafers, a.out)
        print(report(dims(a.size, a.wafers)))


if __name__ == "__main__":
    main()
