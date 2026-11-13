"""[최종] 클라우드 데이터 → CATIA 셀(Cell) 조립품 → 도면까지 한 번에.

흐름
  1) data/out/design_params.json 읽기 (클라우드에서 EFEM STEP을 분석해 만든 변수)
  2) 3030 프레임 생성 (EFEM을 둘러쌀 크기)
  3) FFU 생성 (프레임 위)
  4) 새 조립품 EFEM_CELL 에 프레임 + FFU + 비식별화 EFEM STEP 을 불러와 위치 맞춤
  5) 자동 도면 + 이미지

실행:
    python day3/efem_cell.py --params data/out/design_params.json ^
        --step data/deid/LPM_OPENER_deid.stp --summary data/out/LPM_OPENER_deid_summary.json
    (모의 모드: 끝에 --dry-run)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad
from day2 import frame3030 as fr
from day3 import ffu, autodrawing as ad


def move(comp, dx, dy, dz):
    comp.Move.Apply([1, 0, 0, 0, 1, 0, 0, 0, 1, float(dx), float(dy), float(dz)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    ap.add_argument("--step", required=True, help="비식별화된 EFEM STEP")
    ap.add_argument("--summary", required=True, help="step_inspect.py 결과 *_summary.json")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    with open(a.params, encoding="utf-8") as f:
        P = json.load(f)
    with open(a.summary, encoding="utf-8") as f:
        S = json.load(f)
    fp, fu = P["frame3030"], P["ffu"]
    margin = (fp["W"] - S["W_mm"]) / 2

    catia = get_catia(dry_run=a.dry_run)
    with cad.Timer("프레임"):
        frame_dir, _ = fr.build(catia, fp["design"], fp["W"], fp["D"], fp["H"], a.out, fp.get("panel", False))
    with cad.Timer("FFU"):
        c = ffu.calc(fu["X"], fu["Y"], fu["Z"], fans=fu["fans"], velocity=fu["velocity"])
        ffu_dir = ffu.build(catia, c, a.out)
    frame_path = os.path.join(frame_dir, f"FRAME3030_{fp['design'].upper()}.CATProduct")
    ffu_path = os.path.join(ffu_dir, f"FFU_{c['X']:.0f}x{c['Y']:.0f}x{c['Z']:.0f}.CATProduct")

    doc, root = cad.new_product(catia, "EFEM_CELL")
    root.Products.AddComponentsFromFiles([frame_path, ffu_path, os.path.abspath(a.step)], "All")
    top = fp["H"] + (10 if fp.get("panel") else 0)
    move(root.Products.Item(2), (fp["W"] - c["X"]) / 2, (fp["D"] - c["Y"]) / 2, top)     # FFU: 프레임 위 가운데
    bmin = S["bbox_min"]
    move(root.Products.Item(3), margin - bmin[0], (fp["D"] - S["D_mm"]) / 2 - bmin[1], -bmin[2])  # EFEM: 프레임 안 가운데, 바닥 z=0
    root.Update()
    out = cad.make_out_dir(a.out, "EFEM_CELL")
    cell_path = os.path.join(out, "EFEM_CELL.CATProduct")
    doc.SaveAs(cell_path)
    cad.capture(catia, os.path.join(out, "EFEM_CELL_3d.jpg"))
    size = max(fp["W"], fp["D"], top + c["Z"] + 110)
    ad.make_drawing(catia, cell_path, {"title": "EFEM CELL (Frame+FFU+EFEM)", "note": f"source={S['file']}"}, size, out)
    print(f"[최종 완료] {out}")


if __name__ == "__main__":
    main()
