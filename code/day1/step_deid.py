"""STEP 파일 비식별화 스크립트.

- 헤더(FILE_NAME)의 원본 경로/작성자/조직 → 지움
- 부품·조립품 이름(PRODUCT, NEXT_ASSEMBLY_USAGE_OCCURRENCE 등에 나오는 이름) → ASM_0001 / PRT_0001 코드로 교체
- 원래 이름과 코드의 대응표(mapping.csv)는 따로 저장 → 이 파일은 클라우드에 올리지 않는다!

형상(좌표, 면, 곡선)은 건드리지 않으므로 CATIA에서 열면 모양은 똑같고 이름만 바뀐다.

사용법:
    python day1/step_deid.py data/raw/LPM_OPENER.stp            # 결과: data/deid/LPM_OPENER_deid.stp
    python day1/step_deid.py data/raw/LPM_OPENER.stp               # 여러 파일 한 번에
"""
import argparse
import csv
import glob
import os
import re

from step_bom import iter_entities, refs_of, QUOTED_RE

FILE_NAME_RE = re.compile(r"^FILE_NAME\(.*\);\s*$")


def build_mapping(path, prefix):
    """1차 읽기: 어떤 이름이 조립품(자식이 있음)이고 어떤 이름이 부품인지 판단해서 코드표를 만든다."""
    products, formation, definition, parents = {}, {}, {}, set()
    descs = set()
    for eid, name, args in iter_entities(path):
        if name == "PRODUCT":
            q = QUOTED_RE.findall(args)
            products[eid] = q[0] if q else ""
            descs.update(x for x in q[1:3] if x.strip())
        elif name.startswith("PRODUCT_DEFINITION_FORMATION"):
            formation[eid] = int(refs_of(args)[0])
        elif name == "PRODUCT_DEFINITION":
            definition[eid] = int(refs_of(args)[0])
        elif name == "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
            parents.add(int(refs_of(args)[0]))
    asm_products = {formation.get(definition.get(pd)) for pd in parents}

    mapping = {}
    n_asm = n_prt = 0
    for pid, nm in products.items():
        if not nm or nm in mapping:
            continue
        if pid in asm_products:
            n_asm += 1
            mapping[nm] = f"{prefix}ASM_{n_asm:04d}"
        else:
            n_prt += 1
            mapping[nm] = f"{prefix}PRT_{n_prt:04d}"
    n_desc = 0
    for d in sorted(descs):              # 구매품 품번 같은 설명 문자열도 코드로
        if d not in mapping:
            n_desc += 1
            mapping[d] = f"{prefix}DSC_{n_desc:04d}"
    return mapping


def replace_strings(line, mapping):
    def repl(m):
        s = m.group(1)
        if s in mapping:
            return "'" + mapping[s] + "'"
        base, dot, inst = s.rpartition(".")           # 'D03-E-F-0010.2' 같은 인스턴스 이름
        if dot and inst.isdigit() and base in mapping:
            return "'" + mapping[base] + "." + inst + "'"
        if s.startswith("Symmetry of "):
            rest = s[len("Symmetry of "):]
            if rest in mapping:
                return "'Symmetry of " + mapping[rest] + "'"
        return m.group(0)
    return QUOTED_RE.sub(repl, line)


def deidentify(path, out_dir, prefix=""):
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    mapping = build_mapping(path, prefix)
    out_path = os.path.join(out_dir, f"{stem}_deid.stp")
    with open(path, "r", encoding="latin-1", newline="") as fin, open(out_path, "w", encoding="latin-1", newline="") as fout:
        in_data = False
        for line in fin:
            if not in_data:
                if FILE_NAME_RE.match(line.strip()):
                    eol = "\r\n" if line.endswith("\r\n") else "\n"
                    line = f"FILE_NAME('{stem}_deid.stp','2026-01-01T00:00:00',('none'),('none'),'','','none');{eol}"
                if line.strip() == "DATA;":
                    in_data = True
                fout.write(line)
                continue
            if "'" in line:
                line = replace_strings(line, mapping)
            fout.write(line)
    map_path = os.path.join(out_dir, f"{stem}_mapping.csv")
    with open(map_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["original", "code"])
        for k, v in mapping.items():
            w.writerow([k, v])
    return out_path, map_path, len(mapping)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="data/deid")
    a = ap.parse_args()
    paths = [p for pat in a.files for p in glob.glob(pat)]
    for p in paths:
        out_path, map_path, n = deidentify(p, a.out)
        print(f"[비식별화] {os.path.basename(p)} -> {out_path} (이름 {n}개 교체, 대응표: {map_path})")


if __name__ == "__main__":
    main()
