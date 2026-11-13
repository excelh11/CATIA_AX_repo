"""FFU(Fan Filter Unit) 설계 자동화 (영상: FFU CATIA DESIGNER).

크기·팬 수·목표 면풍속을 넣으면
  ① 풍량/팬 지름/필요 정압/모터 동력을 계산하고 (설계 계산서)
  ② 하우징, 팬 구멍 뚫린 상판, 팬 케이싱, 필터, 타공판을 CATIA 조립품으로 만들고
  ③ CATProduct/CATPart/STEP/이미지/계산서(md)를 저장한다.

실행:
    python day3/ffu.py --preset "1175x575"
    python day3/ffu.py --X 1175 --Y 1175 --fans 2 --velocity 0.45
    python day3/ffu.py --params data/out/design_params.json
    python day3/ffu.py --dry-run
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad

PRESETS = {                     # 이름: (X, Y, 팬 수)
    "575x575": (575, 575, 1),
    "1175x575": (1175, 575, 1),
    "1175x1175": (1175, 1175, 2),
    "1500x900": (1500, 900, 2),
}
FAN_SIZES = [190, 225, 250, 280, 310, 355, 400]   # 상용 팬 지름(mm) 예시
FILTER_DP = {"HEPA": 200.0, "ULPA": 250.0}         # 초기 차압(Pa) 예시
LIMITS = {"X": (400, 1800), "Y": (400, 1400), "Z": (250, 600), "t": (1.0, 2.5),
          "filter_depth": (60, 110), "fans": (1, 4), "velocity": (0.3, 0.6)}


def calc(X, Y, Z=350, t=1.2, filter_depth=70, grade="ULPA", fans=1, fan_dia=0, velocity=0.45):
    """설계 계산. 범위를 벗어나면 ValueError."""
    v = dict(X=X, Y=Y, Z=Z, t=t, filter_depth=filter_depth, fans=fans, velocity=velocity)
    for k, (lo, hi) in LIMITS.items():
        if not lo <= v[k] <= hi:
            raise ValueError(f"{k}={v[k]} 은(는) 허용 범위 {lo}~{hi} 를 벗어났습니다")
    fans = int(fans)
    area = X * Y / 1e6                              # 필터 면적 m²
    Q = area * velocity * 3600                      # 풍량 m³/h
    q = Q / fans                                    # 팬 1대 풍량
    if fan_dia <= 0:                                # 자동: 팬 출구 풍속 약 6 m/s 기준
        need = math.sqrt(4 * (q / 3600 / 6.0) / math.pi) * 1000
        fan_dia = next((d for d in FAN_SIZES if d >= need), FAN_SIZES[-1])
    pitch_x = X / fans
    if fan_dia + 40 > min(pitch_x, Y):
        raise ValueError(f"팬 지름 {fan_dia}mm 가 들어갈 공간이 부족합니다 (팬 수를 늘리거나 크기를 키우세요)")
    dp = FILTER_DP.get(grade, 250.0) + 50           # 필터 + 하우징 손실
    power = (Q / 3600) * dp / 0.5                   # 효율 50% 가정, W
    fan_xy = [((i + 0.5) * pitch_x, Y / 2) for i in range(fans)]
    return {"X": X, "Y": Y, "Z": Z, "t": t, "filter_depth": filter_depth, "grade": grade,
            "fans": fans, "fan_dia": fan_dia, "velocity": velocity, "area_m2": round(area, 3),
            "Q_m3h": round(Q, 1), "q_per_fan_m3h": round(q, 1), "static_Pa": dp,
            "power_W": round(power, 1), "fan_xy": fan_xy}


def parts_layout(c):
    """부품 이름 → (상자들, 원/다각형 돌출 목록, 색)"""
    X, Y, Z, t, fd = c["X"], c["Y"], c["Z"], c["t"], c["filter_depth"]
    r = c["fan_dia"] / 2
    L = {}
    L["Housing"] = ([(0, 0, 0, t, Y, Z), (X - t, 0, 0, t, Y, Z),
                     (t, 0, 0, X - 2 * t, t, Z), (t, Y - t, 0, X - 2 * t, t, Z)], [], (200, 205, 210))
    # 상판: 바깥 사각형 + 팬 구멍(원) → 한 번에 돌출하면 구멍 뚫린 판
    L["Top_Cover_With_Holes"] = ([], [("Z", Z - t, t, cad.rect(0, 0, X, Y), [(x, y, r) for x, y in c["fan_xy"]])],
                                 (185, 190, 198))
    for i, (x, y) in enumerate(c["fan_xy"], 1):
        L[f"Fan_Casing_{i}"] = ([], [("Z", Z, 110, None, [(x, y, r + 6), (x, y, r)])], (70, 75, 85))   # 링
        L[f"Motor_Hub_{i}"] = ([], [("Z", Z + 40, 60, None, [(x, y, r * 0.3)])], (40, 40, 45))
    L["Filter"] = ([(t, t, t + 5, X - 2 * t, Y - 2 * t, fd)], [], (235, 235, 225))
    # 타공판: 25mm 간격 Ø8 구멍 (너무 많으면 간격을 넓힘)
    pitch = 25.0
    while (X // pitch) * (Y // pitch) > 900:
        pitch += 5
    holes = [(x, y, 4.0)
             for x in [pitch / 2 + i * pitch for i in range(int((X - 20) // pitch))] if 15 < x < X - 15
             for y in [pitch / 2 + j * pitch for j in range(int((Y - 20) // pitch))] if 15 < y < Y - 15]
    L["Bottom_Punch_Plate"] = ([], [("Z", 0, t, cad.rect(t, t, X - 2 * t, Y - 2 * t), holes)], (160, 165, 175))
    return L


def to_boxes(c):
    out = []
    for name, (boxes, prof, rgb) in parts_layout(c).items():
        col = tuple(v / 255 for v in rgb)
        if name in ("Housing", "Top_Cover_With_Holes"):
            col = col + (0.3,)
        for (x, y, z, a, b, h) in boxes:
            out.append((x, y, z, a, b, h, col))
        for (axis, start, length, outline, circles) in prof:
            if outline:
                xs = [p[0] for p in outline]; ys = [p[1] for p in outline]
                out.append((min(xs), min(ys), start, max(xs) - min(xs), max(ys) - min(ys), length, col))
            elif circles:
                x, y, rr = circles[0]
                out.append((x - rr * 0.886, y - rr * 0.886, start, rr * 1.772, rr * 1.772, length, col))
    return out


def report(c):
    return "\n".join([
        f"# FFU 설계 계산서 ({c['X']:.0f} x {c['Y']:.0f} mm)", "",
        "| 항목 | 값 |", "|---|---|",
        f"| 필터 등급 / 면적 | {c['grade']} / {c['area_m2']} m² |",
        f"| 목표 면풍속 | {c['velocity']} m/s |",
        f"| 필요 풍량 Q = 면적 × 면풍속 × 3600 | {c['Q_m3h']} m³/h |",
        f"| 팬 수 / 팬 1대 풍량 | {c['fans']}대 / {c['q_per_fan_m3h']} m³/h |",
        f"| 팬 지름 | Ø{c['fan_dia']} mm |",
        f"| 필요 정압 (필터+하우징) | {c['static_Pa']} Pa |",
        f"| 모터 동력 추정 (효율 50%) | {c['power_W']} W |",
        "", "※ 수업용 간이 계산입니다. 실제 선정은 팬 제조사 성능곡선으로 확인하세요."])


def build(catia, c, out_base="output"):
    name = f"FFU_{c['X']:.0f}x{c['Y']:.0f}x{c['Z']:.0f}"
    print(f"[계산] {name}: Q={c['Q_m3h']} m³/h, 팬 {c['fans']}대 Ø{c['fan_dia']}, 정압 {c['static_Pa']} Pa")
    doc, root = cad.new_product(catia, name)
    catia.RefreshDisplay = False
    try:
        for pname, (boxes, prof, rgb) in parts_layout(c).items():
            comp, part = cad.add_part(root, f"{name}_{pname}")
            for i, (x, y, z, a, b, h) in enumerate(boxes, 1):
                cad.box(part, x, y, z, a, b, h, name=f"{pname}_{i}")
            for i, (axis, start, length, outline, circles) in enumerate(prof, 1):
                cad.extrude(part, axis, start, length, outline=outline, circles=circles, name=f"{pname}_P{i}")
            cad.finish(part)
            cad.set_color(doc, comp, rgb)
    finally:
        catia.RefreshDisplay = True
    root.Update()
    out = cad.make_out_dir(out_base, name)
    cad.save_assembly(doc, out)
    cad.export_step(doc, os.path.join(out, f"{name}.stp"))
    cad.capture(catia, os.path.join(out, f"{name}.jpg"))
    with open(os.path.join(out, f"{name}_계산서.md"), "w", encoding="utf-8") as f:
        f.write(report(c))
    with open(os.path.join(out, f"{name}_params.json"), "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    print(f"[완료] {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--X", type=float, default=1175)
    ap.add_argument("--Y", type=float, default=575)
    ap.add_argument("--Z", type=float, default=350)
    ap.add_argument("--t", type=float, default=1.2)
    ap.add_argument("--filter-depth", type=float, default=70)
    ap.add_argument("--grade", default="ULPA", choices=list(FILTER_DP))
    ap.add_argument("--fans", type=int, default=1)
    ap.add_argument("--fan-dia", type=float, default=0, help="0이면 자동 선정")
    ap.add_argument("--velocity", type=float, default=0.45)
    ap.add_argument("--params", help="design_params.json (ffu 항목 사용)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    X, Y, fans = a.X, a.Y, a.fans
    Z, vel = a.Z, a.velocity
    if a.preset:
        X, Y, fans = PRESETS[a.preset]
    if a.params:
        with open(a.params, encoding="utf-8") as f:
            p = json.load(f)["ffu"]
        X, Y, Z, fans, vel = p["X"], p["Y"], p["Z"], p["fans"], p["velocity"]
        print(f"[변수] JSON에서 읽음: {p}")
    c = calc(X, Y, Z, a.t, a.filter_depth, a.grade, fans, a.fan_dia, vel)
    print(report(c))
    build(get_catia(dry_run=a.dry_run), c, a.out)


if __name__ == "__main__":
    main()
