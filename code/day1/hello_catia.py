"""Python → CATIA 첫 연결: 변수 값으로 블록 하나 만들기.

실행:
    python day1/hello_catia.py                      # 기본값 100 x 60 x 20, 구멍 Ø10
    python day1/hello_catia.py --w 150 --h 30       # 값만 바꿔서 다시 실행 → 형상이 바뀐다
    python day1/hello_catia.py --params data/out/design_params.json   # 클라우드에서 받은 JSON 값 사용
    python day1/hello_catia.py --dry-run            # CATIA 없이 흐름만 점검
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=float, default=100.0, help="가로(mm)")
    ap.add_argument("--d", type=float, default=60.0, help="세로(mm)")
    ap.add_argument("--h", type=float, default=20.0, help="두께(mm)")
    ap.add_argument("--hole", type=float, default=10.0, help="구멍 지름(mm), 0이면 없음")
    ap.add_argument("--params", help="design_params.json 경로(있으면 그 값 사용)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    w, d, h, hole = a.w, a.d, a.h, a.hole
    if a.params:
        with open(a.params, encoding="utf-8") as f:
            p = json.load(f)["hello_block"]
        w, d, h, hole = p["w"], p["d"], p["h"], p["hole"]
        print(f"[변수] JSON에서 읽음: {p}")

    catia = get_catia(dry_run=a.dry_run)
    doc, part = cad.new_part(catia, "HELLO_BLOCK")

    # 1단계: 바닥면(Z=0)에서 위로 Pad → 솔리드 블록 생성
    cad.extrude(part, "Z", 0, h, outline=cad.rect(0, 0, w, d), name="Block")
    # 2단계: 윗면(Z=h)에서 아래로 Pocket → 구멍 관통
    if hole > 0:
        cad.extrude(part, "Z", h, h, circles=[(w / 2, d / 2, hole / 2)], pocket=True, name="Block_hole")
    cad.finish(part)

    out = cad.make_out_dir(a.out, "hello")
    doc.SaveAs(os.path.join(out, "HELLO_BLOCK.CATPart"))
    cad.export_step(doc, os.path.join(out, "HELLO_BLOCK.stp"))
    cad.capture(catia, os.path.join(out, "HELLO_BLOCK.jpg"))
    print(f"[완료] {w} x {d} x {h} mm 블록, 구멍 Ø{hole} → {out}")


if __name__ == "__main__":
    main()
