"""CATIA_AutoDrawing GUI - 파트를 선택하면 도면과 이미지가 생성됨.

실행:  python day3/autodrawing_gui.py           (모의 모드: --dry-run)
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from day3 import autodrawing as ad

FONT = ("Malgun Gothic", 10)
TYPES = [("CATIA/STEP", "*.CATPart *.CATProduct *.stp *.step"), ("모든 파일", "*.*")]


class AutoDrawingApp:
    def __init__(self, dry_run=False):
        self.dry_run, self.catia = dry_run, None
        self.root = tk.Tk()
        self.root.title("CATIA AutoDrawing")
        self.root.geometry("860x600")
        head = tk.Frame(self.root, bg="#1f3347"); head.pack(fill="x")
        tk.Label(head, text="파트를 선택하면 도면과 이미지가 생성됨", fg="white", bg="#1f3347",
                 font=("Malgun Gothic", 16, "bold")).pack(anchor="w", padx=14, pady=10)
        form = ttk.Frame(self.root); form.pack(fill="x", padx=12, pady=8)
        self.v = {}
        rows = [("file", "CATPart/CATProduct/STEP 경로", ""), ("title", "도면 제목", ""), ("number", "도면 번호", ""),
                ("company", "회사/소속", "이젠아카데미"), ("designer", "설계자", ""),
                ("size", "모델 최대 치수 mm (0=1:10)", "0"), ("note", "주기(메모)", "")]
        for r, (k, label, d) in enumerate(rows):
            ttk.Label(form, text=label, font=FONT).grid(row=r, column=0, sticky="w", pady=3)
            self.v[k] = tk.StringVar(value=d)
            ttk.Entry(form, textvariable=self.v[k], width=70).grid(row=r, column=1, padx=6, pady=3)
        ttk.Button(form, text="선택", command=self.pick).grid(row=0, column=2)
        self.scale_lbl = ttk.Label(form, text="", font=FONT); self.scale_lbl.grid(row=5, column=2)
        self.v["size"].trace_add("write", lambda *a: self.show_scale())
        bar = ttk.Frame(self.root); bar.pack(fill="x", padx=12)
        ttk.Button(bar, text="CATIA 연결 확인", command=self.connect).pack(side="left", padx=3)
        ttk.Button(bar, text="도면 생성 / 설정 변경 후 다시 생성", command=self.run).pack(side="left", padx=3)
        ttk.Button(bar, text="폴더 일괄 생성", command=self.batch).pack(side="left", padx=3)
        ttk.Button(bar, text="결과 폴더 열기", command=self.open_folder).pack(side="left", padx=3)
        self.log_box = tk.Text(self.root, height=16, bg="#14202c", fg="#d7e3ee", font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=10)
        self.log("CATIA V5를 실행한 상태에서 파일을 고르고 [도면 생성]을 누르세요.")
        self.show_scale()

    def log(self, m):
        self.log_box.insert("end", m + "\n"); self.log_box.see("end"); self.root.update_idletasks()

    def show_scale(self):
        try:
            self.scale_lbl.config(text=f"→ 축척 1:{ad.auto_scale(float(self.v['size'].get() or 0))}")
        except ValueError:
            self.scale_lbl.config(text="숫자 입력")

    def pick(self):
        p = filedialog.askopenfilename(filetypes=TYPES)
        if p:
            self.v["file"].set(p)
            if not self.v["title"].get():
                self.v["title"].set(os.path.splitext(os.path.basename(p))[0])

    def connect(self):
        try:
            self.catia = get_catia(dry_run=self.dry_run); self.log("CATIA 연결 성공")
        except Exception as e:
            self.log(f"[연결 실패] {e}")

    def _info(self):
        return {k: self.v[k].get() for k in ("title", "number", "company", "designer", "note") if self.v[k].get()}

    def run(self, path=None):
        path = path or self.v["file"].get()
        if not path or not os.path.exists(path):
            self.log("[확인 필요] 파일을 먼저 선택하세요"); return
        if self.catia is None:
            self.connect()
        try:
            out = ad.make_drawing(self.catia, path, self._info(), float(self.v["size"].get() or 0))
            self.log(f"[완료] {out}")
        except Exception as e:
            self.log(f"[오류] {e}")

    def batch(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        names = sorted(os.listdir(folder))
        cad_stems = {os.path.splitext(f)[0] for f in names if f.lower().endswith((".catpart", ".catproduct"))}
        files, skipped = [], []
        for f in names:
            low, stem = f.lower(), os.path.splitext(f)[0]
            if low.endswith((".catpart", ".catproduct")):
                files.append(os.path.join(folder, f))
            elif low.endswith((".stp", ".step")):
                # 같은 이름의 CATPart/CATProduct 가 있으면 STEP 은 건너뛴다 (같은 도면 이름으로 겹치기 때문)
                (skipped if stem in cad_stems else files).append(os.path.join(folder, f))
        self.log(f"{len(files)}개 파일 일괄 생성 시작" + (f" (같은 이름 STEP {len(skipped)}개 건너뜀)" if skipped else ""))
        for p in files:
            self.run(p)

    def open_folder(self):
        p = self.v["file"].get()
        if p and os.name == "nt":
            os.startfile(os.path.dirname(p))

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    AutoDrawingApp(dry_run="--dry-run" in sys.argv).mainloop()
