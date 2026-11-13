"""CATIA_AutoDrawing - 파트/조립품/STEP을 고르면 도면(4개 뷰 + 표제란)과 이미지를 자동 생성.

결과 (같은 폴더):
    <이름>.CATDrawing   CATIA 도면
    <이름>.pdf          도면 PDF
    <이름>_drawing.jpg  도면 이미지
    <이름>_3d.jpg       3D 등각 이미지

실행:
    python day3/autodrawing.py output/xxx/FRAME3030_BOX.CATProduct --title "박스 프레임" --size 600
    python day3/autodrawing.py data/deid/LPM_OPENER_deid.stp --size-json data/out/LPM_OPENER_deid_summary.json
    python day3/autodrawing.py "output/*/*.CATProduct"          # 여러 개 한 번에(배치)
    python day3/autodrawing.py sample.CATPart --dry-run
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import cad

SCALES = [1, 2, 5, 10, 20, 50, 100]
VIEW_FIT_MM = 110.0            # A3 한 칸에 들어갈 뷰 크기
# A3 가로(420 x 297) 기준 뷰 위치 — 제3각법(정면 기준 위=평면, 오른쪽=우측면)
LAYOUT = {
    "Front": (95, 105, "front", (1, 0, 0, 0, 0, 1)),
    "Top": (95, 225, "front", (1, 0, 0, 0, 1, 0)),
    "Right": (225, 105, "front", (0, 1, 0, 0, 0, 1)),
    "Iso": (350, 195, "iso", (0.7071, 0.7071, 0, -0.4082, 0.4082, 0.8165)),
}


def auto_scale(max_dim):
    """모델 최대 치수(mm) → 1:s 축척. 0 이하면 1:10."""
    if max_dim <= 0:
        return 10
    return next((s for s in SCALES if max_dim / s <= VIEW_FIT_MM), SCALES[-1])


def title_block(view, info, scale):
    """배경 뷰에 표제란(오른쪽 아래) 선과 글자 넣기."""
    x0, y0, w, h = 290, 5, 125, 45
    f = view.Factory2D
    for (a, b, c, d) in [(x0, y0, x0 + w, y0), (x0 + w, y0, x0 + w, y0 + h), (x0 + w, y0 + h, x0, y0 + h),
                         (x0, y0 + h, x0, y0), (x0, y0 + 15, x0 + w, y0 + 15), (x0, y0 + 30, x0 + w, y0 + 30),
                         (x0 + 62, y0, x0 + 62, y0 + 30)]:
        f.CreateLine(a, b, c, d)
    texts = [(info.get("title", ""), x0 + 3, y0 + 42),
             (f"도면번호: {info.get('number', '')}", x0 + 3, y0 + 27),
             (f"축척 1:{scale}", x0 + 65, y0 + 27),
             (f"회사: {info.get('company', '')}", x0 + 3, y0 + 12),
             (f"설계: {info.get('designer', '')}", x0 + 65, y0 + 12)]
    for (t, x, y) in texts:
        txt = view.Texts.Add(t, x, y)
        try:
            txt.SetFontSize(0, 0, 3.5)
        except Exception:
            pass
    note = info.get("note", "")
    if note:
        view.Texts.Add(f"주기: {note}", 20, 20)


def _close_if_open(catia, path):
    """같은 경로의 문서가 CATIA 에 이미 열려 있으면 닫는다.
    CATIA 는 열려 있는 파일 위에 SaveAs 로 덮어쓸 수 없다 (SaveAs 메소드가 실패했습니다)."""
    target = os.path.normcase(os.path.abspath(path))
    docs = catia.Documents
    for i in range(docs.Count, 0, -1):
        try:
            d = docs.Item(i)
            if os.path.normcase(d.FullName) == target:
                d.Close()
        except Exception:
            pass


def make_drawing(catia, path, info=None, max_dim=0, out_dir=None):
    info = dict(info or {})
    path = os.path.abspath(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    info.setdefault("title", stem)
    info.setdefault("number", f"AD-{time.strftime('%Y%m%d')}-{stem[:12]}")
    out_dir = out_dir or os.path.dirname(path)
    os.makedirs(out_dir, exist_ok=True)
    scale = auto_scale(max_dim)
    print(f"[도면] {os.path.basename(path)} → 축척 1:{scale}")

    model_doc = catia.Documents.Open(path)          # .CATPart / .CATProduct / .stp 모두 가능
    model = model_doc.Product
    cad.capture(catia, os.path.join(out_dir, f"{stem}_3d.jpg"))

    drw = catia.Documents.Add("Drawing")
    sheet = drw.Sheets.ActiveSheet
    try:
        sheet.PaperSize = 3        # 3 = catPaperA3
        sheet.Orientation = 1      # 1 = catPaperLandscape
    except Exception as e:
        print(f"  (용지 설정 건너뜀: {e})")
    views = sheet.Views
    for vname, (x, y, kind, d) in LAYOUT.items():
        view = views.Add(f"{vname} View")
        view.x, view.y = x, y
        view.Scale = 1.0 / scale
        gb = view.GenerativeBehavior
        gb.Document = model
        if kind == "iso":
            gb.DefineIsometricView(*d)
        else:
            gb.DefineFrontView(*d)
        gb.Update()
    bg = views.Item(2)                               # 2번 = 배경(Background) 뷰
    bg.Activate()
    title_block(bg, info, scale)
    views.Item(1).Activate()
    sheet.Update()

    drw_path = os.path.join(out_dir, f"{stem}.CATDrawing")
    _close_if_open(catia, drw_path)                  # 앞에서 만든 같은 이름 도면이 열려 있으면 먼저 닫기
    drw.SaveAs(drw_path)
    drw.ExportData(os.path.join(out_dir, f"{stem}.pdf"), "pdf")
    try:
        catia.ActiveWindow.ActiveViewer.Reframe()
        catia.ActiveWindow.ActiveViewer.CaptureToFile(5, os.path.join(out_dir, f"{stem}_drawing.jpg"))
    except Exception as e:
        print(f"  (도면 이미지 건너뜀: {e})")
    print(f"[완료] {drw_path}")
    return drw_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--title", default="")
    ap.add_argument("--number", default="")
    ap.add_argument("--company", default="이젠아카데미")
    ap.add_argument("--designer", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--size", type=float, default=0, help="모델 최대 치수(mm). 0이면 1:10")
    ap.add_argument("--size-json", help="step_inspect.py가 만든 *_summary.json (W/D/H 사용)")
    ap.add_argument("--out", help="저장 폴더 (기본: 원본과 같은 폴더)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    size = a.size
    if a.size_json:
        with open(a.size_json, encoding="utf-8") as f:
            s = json.load(f)
        size = max(s["W_mm"], s["D_mm"], s["H_mm"])
    paths = [p for pat in a.files for p in (glob.glob(pat) or [pat])]
    catia = get_catia(dry_run=a.dry_run)
    info = {k: getattr(a, k) for k in ("title", "number", "company", "designer", "note") if getattr(a, k)}
    for p in paths:
        make_drawing(catia, p, info, size, a.out)


if __name__ == "__main__":
    main()
