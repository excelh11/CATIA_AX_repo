"""[데이터 담당] 학습용 이미지 만들기 — 부품 STEP → 부품(솔리드)마다 6방향 이미지.

폴더 이름이 곧 정답(라벨)이다:
    ai/data/raw/bolt/*.stp       →  ai/data/images/bolt/<파일>_s001_v0.png …
    ai/data/raw/profile/*.stp    →  ai/data/images/profile/…

실행 (AWS 조 서버 터미널, venv 켠 상태 — OCP 필요):
    cd ~/CATIA_AX
    python ai/render_dataset.py                         # ai/data/raw → ai/data/images
    python ai/render_dataset.py --demo 40               # AI HUB 데이터 전: 연습용 가짜 부품 4종 × 40개

AI HUB(https://www.aihub.or.kr) 제조·로보틱스 데이터셋의 '기계부품 CAD' STEP 을
종류별 폴더로 나눠 ai/data/raw/ 아래에 넣는 것이 데이터 담당의 첫 일이다.
"""
import argparse
import glob
import os
import time

import numpy as np

from mesh_views import DEMO_CLASSES, demo_part, render_views, split_solids

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="부품 STEP → 학습용 다방향 이미지")
    ap.add_argument("--raw", default=os.path.join(HERE, "data", "raw"))
    ap.add_argument("--out", default=os.path.join(HERE, "data", "images"))
    ap.add_argument("--size", type=int, default=128, help="이미지 한 변 픽셀")
    ap.add_argument("--deflection", type=float, default=2.0, help="메쉬 거칠기 mm (작을수록 정밀 · 느림)")
    ap.add_argument("--demo", type=int, default=0, help="가짜 부품을 종류마다 N개 만든다 (OCP 불필요)")
    a = ap.parse_args()

    t0, total = time.time(), 0
    if a.demo:
        rng = np.random.default_rng(0)
        for label in DEMO_CLASSES:
            os.makedirs(os.path.join(a.out, label), exist_ok=True)
            for i in range(a.demo):
                render_views(demo_part(label, rng), os.path.join(a.out, label, f"demo_{label}_s{i:03d}"), a.size)
                total += 1
            print(f"  {label:10s} {a.demo}개")
    else:
        labels = sorted(d for d in os.listdir(a.raw) if os.path.isdir(os.path.join(a.raw, d))) \
            if os.path.isdir(a.raw) else []
        if not labels:
            raise SystemExit(f"{a.raw} 아래에 종류별 폴더(예: bolt/, profile/)를 만들고 STEP 을 넣으세요")
        for label in labels:
            os.makedirs(os.path.join(a.out, label), exist_ok=True)
            files = sorted(glob.glob(os.path.join(a.raw, label, "*.st*p")))
            n = 0
            for f in files:
                stem = os.path.splitext(os.path.basename(f))[0]
                try:
                    parts = split_solids(f, a.deflection)
                except Exception as e:                       # 깨진 STEP 하나 때문에 멈추지 않는다
                    print(f"  [건너뜀] {os.path.basename(f)}: {e}")
                    continue
                for i, (tris, _) in enumerate(parts, 1):
                    render_views(tris, os.path.join(a.out, label, f"{stem}_s{i:03d}"), a.size)
                    n += 1
            print(f"  {label:10s} STEP {len(files)}개 → 부품 {n}개")
            total += n
    print(f"[완료] 부품 {total}개 × 6방향 이미지 → {a.out}  ({time.time() - t0:.0f}초)")


if __name__ == "__main__":
    main()
