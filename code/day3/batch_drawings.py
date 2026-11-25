"""폴더 일괄 도면 — autodrawing_gui.py 의 [폴더 일괄 생성] 버튼과 같은 일을 명령 한 줄로 (README ③).

폴더 안의 CATPart · CATProduct 마다 A3 4면도(CATDrawing) + PDF + 이미지를 만든다.
같은 이름의 CATPart/CATProduct 가 있는 STEP 은 건너뛴다 (도면 이름이 겹치기 때문 — GUI 와 같은 규칙).

실행 (CMD, CATIA V5 켠 상태):
    cd C:\\CATIA_AX\\code
    python day3\\batch_drawings.py output\\20261123_154805_FRAME3030_BOX
    (모의 모드: 끝에 --dry-run)
run_full_flowup.py 는 자동화 마지막 단계에서 프레임 폴더로 이 파일을 자동 실행한다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from day3 import autodrawing as ad


def collect(folder):
    """GUI [폴더 일괄 생성] 과 같은 규칙으로 도면을 만들 파일 목록을 고른다."""
    names = sorted(os.listdir(folder))
    cad_stems = {os.path.splitext(f)[0] for f in names if f.lower().endswith((".catpart", ".catproduct"))}
    files, skipped = [], []
    for f in names:
        low, stem = f.lower(), os.path.splitext(f)[0]
        if low.endswith((".catpart", ".catproduct")):
            files.append(os.path.join(folder, f))
        elif low.endswith((".stp", ".step")):
            (skipped if stem in cad_stems else files).append(os.path.join(folder, f))
    return files, skipped


def main():
    ap = argparse.ArgumentParser(description="폴더 안 부품 전부의 도면을 한 번에 (README ③)")
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--company", default="이젠아카데미")
    ap.add_argument("--designer", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--size", type=float, default=0, help="모델 최대 치수(mm). 0이면 1:10 (GUI 기본값과 같음)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    info = {k: getattr(a, k) for k in ("company", "designer", "note") if getattr(a, k)}
    catia = get_catia(dry_run=a.dry_run)
    done, failed = 0, []
    for folder in a.folders:
        if not os.path.isdir(folder):
            print(f"[확인 필요] 폴더가 없습니다: {folder}")
            failed.append(folder)
            continue
        files, skipped = collect(folder)
        print(f"[일괄] {folder}\n  {len(files)}개 파일 일괄 생성 시작"
              + (f" (같은 이름 STEP {len(skipped)}개 건너뜀)" if skipped else ""))
        if not files and not a.dry_run:
            print(f"[확인 필요] 도면을 만들 CATPart · CATProduct 가 없습니다: {folder}")
            failed.append(folder)
        for i, p in enumerate(files, 1):
            print(f"  ({i}/{len(files)}) ", end="")
            try:
                ad.make_drawing(catia, p, info, a.size)
                done += 1
            except Exception as e:                 # 한 부품이 실패해도 나머지는 계속
                print(f"  [오류] {os.path.basename(p)}: {e}")
                failed.append(p)
    print(f"[일괄 완료] 도면 {done}개" + (f", 실패 {len(failed)}개" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
