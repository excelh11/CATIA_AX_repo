"""[파이프라인 담당] 비식별 STEP → 부품마다 종류 예측 → 자동 BOM.

부품 이름은 비식별화로 지워졌지만(PRT_0001 …), 모양을 보고 종류를 맞힌다.
부품(솔리드)마다 6방향 이미지를 만들어 예측한 뒤 확률을 평균한다.

실행 (AWS 서버 — OCP + torch 필요. GPU 없어도 예측은 CPU 로 충분):
    cd ~/CATIA_AX
    python ai/predict_bom.py code/data/deid/LPM_OPENER_deid.stp
    python ai/predict_bom.py --demo 5                       # STEP 없이 가짜 부품으로 시험

결과 (code/data/out/):
    <stem>_bom_pred.csv    부품마다  solid_id · 종류 · 확신도 · 외곽 W/D/H(mm)
    <stem>_bom_pred.json   종류별 개수 요약  →  make_params · CATIA 도면 BOM 표에서 사용 (팀 과제)
"""
import argparse
import csv
import json
import os
import tempfile
from collections import Counter

import numpy as np
import torch
from PIL import Image
from torchvision import models

from mesh_views import DEMO_CLASSES, demo_part, render_views, split_solids
from train_classifier import TF_EVAL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_model(path, dev):
    ck = torch.load(path, map_location=dev)
    net = models.resnet18(weights=None)
    net.fc = torch.nn.Linear(net.fc.in_features, len(ck["classes"]))
    net.load_state_dict(ck["state_dict"])
    return net.to(dev).eval(), ck["classes"]


@torch.no_grad()
def predict_part(net, dev, tris, tmp, sid):
    paths = render_views(tris, os.path.join(tmp, sid))
    x = torch.stack([TF_EVAL(Image.open(p)) for p in paths]).to(dev)
    prob = net(x).softmax(1).mean(0)            # 6방향 평균
    conf, k = prob.max(0)
    return int(k), float(conf)


def main():
    ap = argparse.ArgumentParser(description="비식별 STEP → 부품 종류 예측 → 자동 BOM")
    ap.add_argument("step", nargs="?", help="비식별 STEP (예: code/data/deid/LPM_OPENER_deid.stp)")
    ap.add_argument("--model", default=os.path.join(HERE, "models", "part_cls.pt"))
    ap.add_argument("--out", default=os.path.join(ROOT, "code", "data", "out"))
    ap.add_argument("--min-conf", type=float, default=0.6, help="이보다 낮으면 '미확인'")
    ap.add_argument("--deflection", type=float, default=2.0)
    ap.add_argument("--demo", type=int, default=0, help="STEP 대신 가짜 부품을 종류마다 N개")
    a = ap.parse_args()
    if not a.step and not a.demo:
        ap.error("STEP 파일 경로 또는 --demo N 을 주세요")
    if a.step and not a.step.endswith("_deid.stp"):
        ap.error("비식별 파일(..._deid.stp)만 사용합니다")

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net, classes = load_model(a.model, dev)
    if a.demo:
        rng = np.random.default_rng(123)
        parts = [(demo_part(c, rng), None, c) for c in DEMO_CLASSES for _ in range(a.demo)]
        stem = "demo"
    else:
        parts = [(t, size, None) for t, size in split_solids(a.step, a.deflection)]
        stem = os.path.splitext(os.path.basename(a.step))[0]
    print(f"[예측] 부품 {len(parts)}개 · 종류 {classes} · {dev}")

    rows, hits = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, (tris, size, truth) in enumerate(parts, 1):
            sid = f"S{i:04d}"
            k, conf = predict_part(net, dev, tris, tmp, sid)
            label = classes[k] if conf >= a.min_conf else "미확인"
            if size is None:
                pts = np.asarray(tris).reshape(-1, 3)
                size = (pts.max(0) - pts.min(0)).round(1).tolist()
            rows.append({"solid_id": sid, "label": label, "conf": round(conf, 3),
                         "W": size[0], "D": size[1], "H": size[2], **({"truth": truth} if truth else {})})
            hits += int(truth == label) if truth else 0
            if i % 50 == 0:
                print(f"  {i}/{len(parts)}")

    os.makedirs(a.out, exist_ok=True)
    csv_path = os.path.join(a.out, f"{stem}_bom_pred.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    counts = Counter(r["label"] for r in rows)
    summary = {"source": a.step or "demo", "n_parts": len(rows), "counts": dict(counts.most_common()),
               "model_classes": classes, "min_conf": a.min_conf}
    if a.demo:
        summary["demo_accuracy"] = round(hits / len(rows), 3)
    with open(os.path.join(a.out, f"{stem}_bom_pred.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[자동 BOM] " + " · ".join(f"{k} {v}" for k, v in counts.most_common()))
    if a.demo:
        print(f"[연습 정확도] {summary['demo_accuracy'] * 100:.1f}%")
    print(f"[저장] {csv_path}")


if __name__ == "__main__":
    main()
