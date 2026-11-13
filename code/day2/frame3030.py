"""3030 알루미늄 프로파일 프레임 자동 생성 (영상: CATIA TABLE / FRAME 3030).

치수(W, D, H)와 디자인을 고르면
  ① 프로파일 절단 목록(BOM)을 계산하고
  ② CATIA에 프로파일 1개 = 부품 1개로 조립품을 만들고
  ③ CATProduct + CATPart + STEP + 이미지 + 절단표 CSV 를 저장한다.

실행:
    python day2/frame3030.py --design box --W 600 --D 500 --H 600
    python day2/frame3030.py --design bench --W 1200 --D 700 --H 850
    python day2/frame3030.py --params data/out/design_params.json      # 클라우드에서 계산한 값
    python day2/frame3030.py --design gantry --dry-run
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad

P = 30.0          # 프로파일 단면 30 x 30
SLOT_W = 8.2      # T 슬롯 입구 폭
SLOT_D = 8.0      # T 슬롯 깊이(단순화)
CORE_R = 3.4      # 가운데 탭 구멍 (M8 탭 기준 Ø6.8)

DESIGNS = {
    "box": "사각 박스 프레임",
    "bench": "작업대 + 하부 선반",
    "gantry": "문형(갠트리) 프레임",
    "housing2": "2베이 패널 하우징",
}


def profile_section(u0, v0):
    """3030 단면 (좌하단 모서리 u0,v0). 네 변 가운데에 슬롯 홈이 파인 사각형."""
    s, w, d = P, SLOT_W, SLOT_D
    a, b = (s - w) / 2, (s + w) / 2
    pts = [(0, 0), (a, 0), (a, d), (b, d), (b, 0), (s, 0),             # 아래 변 + 홈
           (s, a), (s - d, a), (s - d, b), (s, b), (s, s),              # 오른쪽 변 + 홈
           (b, s), (b, s - d), (a, s - d), (a, s), (0, s),              # 위 변 + 홈
           (0, b), (d, b), (d, a), (0, a)]                              # 왼쪽 변 + 홈
    return [(u0 + x, v0 + y) for x, y in pts], [(u0 + s / 2, v0 + s / 2, CORE_R)]


def members(design, W, D, H):
    """디자인별 프로파일 목록: (이름, 축, 시작위치, 길이, 단면 u0, 단면 v0).
    축 Z 기둥: 단면 (u,v)=(x,y) / 축 X 보: (u,v)=(y,z) / 축 Y 보: (u,v)=(z,x)
    규칙: 기둥이 전체 높이, 가로보는 기둥 사이에 끼움(길이 = 외곽 - 2P)."""
    m = []
    LX, LY = W - 2 * P, D - 2 * P

    def posts(xs, ys, h=H, tag="POST", z0=0):
        for i, (x, y) in enumerate([(x, y) for x in xs for y in ys], 1):
            m.append((f"{tag}_{i:02d}", "Z", z0, h, x, y))

    def ring_x(z, ys, x0=P, length=LX, tag="BEAM_X"):
        for y in ys:
            m.append((f"{tag}_{len(m)+1:02d}", "X", x0, length, y, z))

    def ring_y(z, xs, y0=P, length=LY, tag="BEAM_Y"):
        for x in xs:
            m.append((f"{tag}_{len(m)+1:02d}", "Y", y0, length, z, x))

    if design == "box":
        posts([0, W - P], [0, D - P])
        for z in (0, H - P):
            ring_x(z, [0, D - P]); ring_y(z, [0, W - P])
    elif design == "bench":
        posts([0, W - P], [0, D - P])
        for z in (H - P, 150):                       # 상판 받침 + 하부 선반(바닥에서 150)
            ring_x(z, [0, D - P]); ring_y(z, [0, W - P])
        ring_y(H - P, [W / 2 - P / 2])               # 상판 중앙 보강
    elif design == "gantry":
        posts([0, W - P], [D / 2 - P / 2], h=H - P, z0=P)   # 양쪽 기둥 2개(바닥 다리 위)
        ring_y(0, [0, W - P], y0=0, length=D, tag="FOOT")   # 바닥 다리(Y 방향 전체 길이)
        ring_x(H - P, [D / 2 - P / 2])               # 상부 가로보
        ring_x(H - 200, [D / 2 - P / 2])             # 장착 보
    elif design == "housing2":
        posts([0, W / 2 - P / 2, W - P], [0, D - P])
        half = W / 2 - P / 2 - P                     # 한 칸 안쪽 길이
        for z in (0, H / 2, H - P):
            for x0 in (P, W / 2 + P / 2):
                ring_x(z, [0, D - P], x0=x0, length=half)
            ring_y(z, [0, W / 2 - P / 2, W - P])
    else:
        raise ValueError(f"디자인 없음: {design} (선택: {', '.join(DESIGNS)})")
    return m


def to_boxes(mem, panel=False, W=0, D=0, H=0):
    """미리보기용 상자 목록 (단면은 30x30 사각형으로 단순화)."""
    boxes = []
    for (_, axis, start, length, u0, v0) in mem:
        if axis == "Z":
            boxes.append((u0, v0, start, P, P, length, (0.62, 0.65, 0.70)))
        elif axis == "X":
            boxes.append((start, u0, v0, length, P, P, (0.55, 0.60, 0.68)))
        else:
            boxes.append((v0, start, u0, P, length, P, (0.50, 0.56, 0.64)))
    if panel:
        boxes.append((0, 0, H, W, D, 10, (0.16, 0.55, 0.63)))
    return boxes


def cut_list(mem):
    """같은 길이끼리 묶은 절단표."""
    table = {}
    for name, axis, start, length, *_ in mem:
        table[round(length, 1)] = table.get(round(length, 1), 0) + 1
    return sorted(table.items(), reverse=True)


def check(design, W, D, H):
    msgs = []
    if min(W, D, H) < 4 * P:
        msgs.append(f"치수가 너무 작습니다 (각 변 {4*P:.0f}mm 이상)")
    if max(W, D, H) > 3000:
        msgs.append("3000mm 초과: 프로파일 표준 길이(보통 4000mm) 및 처짐 확인 필요")
    if design == "gantry" and H < 400:
        msgs.append("문형 프레임은 높이 400mm 이상 권장")
    return msgs


def build(catia, design, W, D, H, out_base="output", panel=False):
    mem = members(design, W, D, H)
    total = sum(m[3] for m in mem)
    print(f"[계산] {DESIGNS[design]} {W}x{D}x{H} mm → 프로파일 {len(mem)}개, 총 {total/1000:.2f} m")
    for msg in check(design, W, D, H):
        print("  [!]", msg)

    name = f"FRAME3030_{design.upper()}"
    doc, root = cad.new_product(catia, name)
    catia.RefreshDisplay = False                      # 만드는 동안 화면 갱신 끄기 → 빨라짐
    try:
        for (pname, axis, start, length, u0, v0) in mem:
            comp, part = cad.add_part(root, f"{name}_{pname}_L{int(length)}")
            outline, holes = profile_section(u0, v0)
            cad.extrude(part, axis, start, length, outline=outline, circles=holes, name=f"Profile_L{int(length)}")
            cad.finish(part)
            cad.set_color(doc, comp, (170, 175, 185))
        if panel:                                     # 상판(두께 10) 추가
            comp, part = cad.add_part(root, f"{name}_TOP_PANEL")
            cad.box(part, 0, 0, H, W, D, 10, name="TopPanel")
            cad.finish(part)
            cad.set_color(doc, comp, (40, 140, 160))
    finally:
        catia.RefreshDisplay = True
    root.Update()

    out = cad.make_out_dir(out_base, name)
    cad.save_assembly(doc, out)
    cad.export_step(doc, os.path.join(out, f"{name}.stp"))
    cad.capture(catia, os.path.join(out, f"{name}.jpg"))
    with open(os.path.join(out, f"{name}_cutlist.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["길이(mm)", "수량"])
        w.writerows(cut_list(mem))
    print(f"[완료] 저장 폴더: {out}")
    return out, mem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="box", choices=list(DESIGNS))
    ap.add_argument("--W", type=float, default=600)
    ap.add_argument("--D", type=float, default=500)
    ap.add_argument("--H", type=float, default=600)
    ap.add_argument("--panel", action="store_true", help="상판 추가")
    ap.add_argument("--params", help="design_params.json (frame3030 항목 사용)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    design, W, D, H, panel = a.design, a.W, a.D, a.H, a.panel
    if a.params:
        with open(a.params, encoding="utf-8") as f:
            p = json.load(f)["frame3030"]
        design, W, D, H, panel = p["design"], p["W"], p["D"], p["H"], p.get("panel", False)
        print(f"[변수] JSON에서 읽음: {p}")
    catia = get_catia(dry_run=a.dry_run)
    build(catia, design, W, D, H, a.out, panel)


if __name__ == "__main__":
    main()
