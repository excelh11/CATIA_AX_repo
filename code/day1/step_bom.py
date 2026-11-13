"""STEP(AP214/AP242) 파일에서 조립 구조(BOM)를 뽑아내는 스크립트.

CATIA 없이 표준 라이브러리만 사용하므로 엘리스 클라우드(리눅스)에서 그대로 실행됩니다.

사용법:
    python day1/step_bom.py data/deid/LPM_OPENER_deid.stp      # 결과: data/out/..._bom.csv, _bom.json, _tree.txt
    python day1/step_bom.py "data/deid/*.stp"              # 여러 파일 한 번에
"""
import argparse
import csv
import glob
import json
import os
import re
from collections import Counter, defaultdict

# '#번호=엔티티이름(인자...)' 형태의 한 줄을 읽기 위한 정규식
ENTITY_RE = re.compile(r"^#(\d+)\s*=\s*([A-Z_0-9]+)\s*\((.*)\)\s*;\s*$", re.S)
QUOTED_RE = re.compile(r"'((?:[^']|'')*)'")
REF_RE = re.compile(r"#(\d+)")

def refs_of(args):
    """인자에서 #번호 참조만 뽑는다. 이름 문자열 안의 '#'은 무시(문자열을 먼저 지움)."""
    return REF_RE.findall(QUOTED_RE.sub("''", args))


WANTED = (
    "PRODUCT",
    "PRODUCT_DEFINITION_FORMATION",
    "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
    "PRODUCT_DEFINITION",
    "NEXT_ASSEMBLY_USAGE_OCCURRENCE",
)


def iter_entities(path):
    """STEP 파일을 한 엔티티(;로 끝나는 문장)씩 읽어서 (번호, 이름, 인자문자열)을 돌려준다.
    파일이 수백 MB여도 메모리에 한꺼번에 올리지 않는다."""
    buf = ""
    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            buf = buf + line if buf else line
            if not buf.endswith(";"):
                continue
            if buf.startswith("#"):
                m = ENTITY_RE.match(buf)
                if m:
                    yield int(m.group(1)), m.group(2), m.group(3)
            buf = ""


def parse_bom(path):
    products = {}      # product id -> 이름
    formation = {}     # formation id -> product id
    definition = {}    # product_definition id -> formation id
    usages = []        # (부모 PD, 자식 PD)
    for eid, name, args in iter_entities(path):
        if name not in WANTED:
            continue
        if name == "PRODUCT":
            q = QUOTED_RE.findall(args)
            products[eid] = q[0] if q else f"#{eid}"
        elif name.startswith("PRODUCT_DEFINITION_FORMATION"):
            refs = refs_of(args)
            formation[eid] = int(refs[0])
        elif name == "PRODUCT_DEFINITION":
            refs = refs_of(args)
            definition[eid] = int(refs[0])
        elif name == "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
            refs = refs_of(args)
            usages.append((int(refs[0]), int(refs[1])))

    def pd_name(pd):
        return products.get(formation.get(definition.get(pd)), f"#{pd}")

    children = defaultdict(Counter)
    has_parent = set()
    for parent, child in usages:
        children[parent][child] += 1
        has_parent.add(child)
    roots = [pd for pd in definition if pd not in has_parent and pd in children] or \
            [pd for pd in definition if pd not in has_parent]

    rows = []

    def walk(pd, level, qty):
        kind = "ASSY" if pd in children else "PART"
        rows.append({"level": level, "name": pd_name(pd), "qty": qty, "type": kind})
        for child, n in children.get(pd, {}).items():
            walk(child, level + 1, n)

    for r in roots:
        walk(r, 0, 1)
    return rows


def save(rows, stem, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{stem}_bom.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:   # 엑셀에서 한글이 안 깨지게 utf-8-sig
        w = csv.DictWriter(f, fieldnames=["level", "name", "qty", "type"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out_dir, f"{stem}_bom.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, f"{stem}_tree.txt"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write("  " * r["level"] + f"- {r['name']}  x{r['qty']}  [{r['type']}]\n")
    return csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="data/out")
    a = ap.parse_args()
    paths = [p for pat in a.files for p in glob.glob(pat)]
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        rows = parse_bom(p)
        csv_path = save(rows, stem, a.out)
        n_asm = sum(r["type"] == "ASSY" for r in rows)
        n_part = sum(r["type"] == "PART" for r in rows)
        top = rows[0]["name"] if rows else "-"
        print(f"[BOM] {os.path.basename(p)}: 최상위={top}, 행={len(rows)}, 조립품={n_asm}, 부품={n_part} -> {csv_path}")


if __name__ == "__main__":
    main()
