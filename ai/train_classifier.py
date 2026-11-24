"""[모델 담당] 부품 분류 AI 학습 — GPU 서버에서 실행.

ai/data/images/<종류>/*.png 로 ResNet18(ImageNet 사전학습)을 미세조정한다.
같은 부품의 6방향 이미지가 학습/검증에 나뉘어 들어가면 점수가 부풀려지므로 '부품 단위'로 나눈다.

실행 (AWS GPU 서버 터미널):
    cd ~/CATIA_AX
    python ai/train_classifier.py --epochs 10
    python ai/train_classifier.py --epochs 10 --device cpu      # 같은 학습을 CPU 로 — 시간 비교용

결과:
    ai/models/part_cls.pt        모델 + 종류 이름 (predict_bom.py 가 읽음)
    ai/models/metrics.json       정확도 · 장치 · 학습 시간 · 종류별 정확도
"""
import argparse
import json
import os
import random
import re
import time
from collections import defaultdict

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms

HERE = os.path.dirname(os.path.abspath(__file__))
PART_ID = re.compile(r"_v\d+\.png$")          # 'xxx_s001_v3.png' → 부품 'xxx_s001'

TF_TRAIN = transforms.Compose([
    transforms.Grayscale(3), transforms.Resize((128, 128)),
    transforms.RandomHorizontalFlip(), transforms.RandomRotation(10),
    transforms.ToTensor(), transforms.Normalize([0.5] * 3, [0.5] * 3)])
TF_EVAL = transforms.Compose([
    transforms.Grayscale(3), transforms.Resize((128, 128)),
    transforms.ToTensor(), transforms.Normalize([0.5] * 3, [0.5] * 3)])


def split_by_part(ds, val_ratio, seed):
    """부품 단위로 학습/검증을 나눈다 (같은 부품의 다른 각도가 양쪽에 섞이지 않게)."""
    groups = defaultdict(list)
    for i, (path, _) in enumerate(ds.samples):
        groups[PART_ID.sub("", path)].append(i)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    n_val = max(1, int(len(keys) * val_ratio))
    val = [i for k in keys[:n_val] for i in groups[k]]
    train = [i for k in keys[n_val:] for i in groups[k]]
    return train, val


def main():
    ap = argparse.ArgumentParser(description="부품 분류 AI 학습 (GPU)")
    ap.add_argument("--data", default=os.path.join(HERE, "data", "images"))
    ap.add_argument("--out", default=os.path.join(HERE, "models"))
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val", type=float, default=0.2, help="검증용 부품 비율")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--no-pretrained", action="store_true", help="인터넷이 막혔을 때 (정확도는 낮아짐)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    dev = torch.device(a.device)
    print(f"[장치] {dev}" + (f" · {torch.cuda.get_device_name(0)}" if dev.type == "cuda" else
                            " (GPU 없음 — GPU 서버에서 실행하세요)"))

    ds_train = datasets.ImageFolder(a.data, TF_TRAIN)
    ds_eval = datasets.ImageFolder(a.data, TF_EVAL)
    classes = ds_train.classes
    tr_idx, va_idx = split_by_part(ds_train, a.val, a.seed)
    print(f"[데이터] 종류 {len(classes)}개 {classes} · 학습 이미지 {len(tr_idx)} · 검증 이미지 {len(va_idx)}")
    workers = 4 if dev.type == "cuda" else 0
    dl_tr = DataLoader(Subset(ds_train, tr_idx), a.batch, shuffle=True, num_workers=workers,
                       pin_memory=dev.type == "cuda")
    dl_va = DataLoader(Subset(ds_eval, va_idx), a.batch, num_workers=workers)

    weights = None if a.no_pretrained else models.ResNet18_Weights.DEFAULT
    net = models.resnet18(weights=weights)
    net.fc = nn.Linear(net.fc.in_features, len(classes))
    net.to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
    scaler = torch.amp.GradScaler(enabled=dev.type == "cuda")
    loss_fn = nn.CrossEntropyLoss()

    t0, best = time.time(), (-1.0, None)
    for ep in range(1, a.epochs + 1):
        net.train()
        run_loss = 0.0
        for x, y in dl_tr:
            x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                loss = loss_fn(net(x), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            run_loss += loss.item() * len(y)
        sched.step()
        acc, per_cls = evaluate(net, dl_va, dev, len(classes))
        print(f"  epoch {ep:2d}/{a.epochs}  loss {run_loss / max(1, len(tr_idx)):.3f}  "
              f"검증 정확도 {acc * 100:5.1f}%  ({time.time() - t0:.0f}초)")
        if acc > best[0]:
            best = (acc, per_cls)
            os.makedirs(a.out, exist_ok=True)
            torch.save({"state_dict": net.state_dict(), "classes": classes, "arch": "resnet18"},
                       os.path.join(a.out, "part_cls.pt"))

    elapsed = time.time() - t0
    metrics = {"device": str(dev), "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None,
               "epochs": a.epochs, "train_sec": round(elapsed, 1), "best_val_acc": round(best[0], 4),
               "per_class_acc": {c: round(v, 4) for c, v in zip(classes, best[1])},
               "classes": classes, "n_train_images": len(tr_idx), "n_val_images": len(va_idx)}
    with open(os.path.join(a.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[완료] 최고 검증 정확도 {best[0] * 100:.1f}% · 학습 {elapsed:.0f}초 · {dev}")
    print(f"       {os.path.join(a.out, 'part_cls.pt')}")


@torch.no_grad()
def evaluate(net, dl, dev, n_cls):
    net.eval()
    hit, cnt = torch.zeros(n_cls), torch.zeros(n_cls)
    for x, y in dl:
        p = net(x.to(dev)).argmax(1).cpu()
        for t, q in zip(y, p):
            cnt[t] += 1
            hit[t] += int(t == q)
    per = (hit / cnt.clamp(min=1)).tolist()
    return (hit.sum() / cnt.sum().clamp(min=1)).item(), per


if __name__ == "__main__":
    main()
