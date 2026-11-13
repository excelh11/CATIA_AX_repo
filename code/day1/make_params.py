"""클라우드 분석 결과(형상 요약 + BOM) → CATIA 설계 변수 파일(design_params.json).

EFEM 데이터의 외곽 치수를 읽어서, 그 장비를 둘러싸는 3030 프레임 / 위에 올릴 FFU의 크기를 계산한다.
이 JSON 하나만 로컬 PC로 내려받으면 이후 CATIA 스크립트가 그대로 읽어 쓴다.

사용법:
    python day1/make_params.py --summary data/out/LPM_OPENER_deid_summary.json --bom data/out/LPM_OPENER_deid_bom.csv
"""
import argparse
import csv
import json
import math
import os


def round_up(x, step):
    return int(math.ceil(x / step) * step)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--bom")
    ap.add_argument("--margin", type=float, default=100.0, help="장비와 프레임 사이 여유(mm, 한쪽)")
    ap.add_argument("--out", default="data/out/design_params.json")
    a = ap.parse_args()

    with open(a.summary, encoding="utf-8") as f:
        s = json.load(f)
    n_part = n_asm = 0
    if a.bom:
        with open(a.bom, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["type"] == "PART":
                    n_part += int(r["qty"])
                else:
                    n_asm += 1

    W, D, H = s["W_mm"], s["D_mm"], s["H_mm"]
    frame_w = round_up(W + 2 * a.margin, 50)        # 50mm 단위로 올림
    frame_d = round_up(D + 2 * a.margin, 50)
    frame_h = round_up(H + a.margin, 50)
    params = {
        "source": s["file"],
        "equipment": {"W": W, "D": D, "H": H, "solids": s["solids"], "parts_in_bom": n_part, "assemblies": n_asm},
        "hello_block": {"w": round(W / 10, 1), "d": round(D / 10, 1), "h": 20.0, "hole": 10.0},
        "frame3030": {"design": "box", "W": frame_w, "D": frame_d, "H": frame_h, "panel": True},
        # ffu.py 허용 범위(X 400~1800, Y 400~1400) 안으로 맞춘다. 작은 장비도 최소 400mm.
        "ffu": {"X": min(max(round_up(W * 0.8, 25), 400), 1800), "Y": min(max(round_up(D * 0.5, 25), 400), 1400), "Z": 350,
                "fans": 2, "velocity": 0.45},
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    print(json.dumps(params, ensure_ascii=False, indent=2))
    print(f"[저장] {a.out}  ← 이 파일을 로컬 PC로 내려받으세요")


if __name__ == "__main__":
    main()
