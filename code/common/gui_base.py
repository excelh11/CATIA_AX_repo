"""모든 실습 GUI(프레임/FOUP/FFU/도면)가 함께 쓰는 tkinter 화면 틀.

왼쪽: 입력 칸(폼) / 오른쪽: 미리보기 그림 / 아래: 버튼 줄 + 로그 창
각 도구는 ToolApp을 상속해서 fields(), make_boxes(), run_catia() 만 채우면 된다.
"""
import json
import os
import sys
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.catia_conn import get_catia
from common import preview

FONT = ("Malgun Gothic", 10)


class ToolApp:
    TITLE = "도구"
    SUBTITLE = ""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.catia = None
        self.root = tk.Tk()
        self.root.title(self.TITLE)
        self.root.geometry("1100x760")
        self.vars = {}
        self._build()

    # ---------- 자식 클래스가 채울 부분 ----------
    def fields(self):
        """[(키, 라벨, 기본값, 선택지 또는 None), ...]"""
        return []

    def make_boxes(self, v):
        """입력값 v(dict) → 미리보기 상자 목록. 문제 있으면 ValueError."""
        return []

    def info_text(self, v):
        return ""

    def run_catia(self, v):
        """CATIA에서 실제 생성. 저장 폴더 경로를 돌려준다."""
        raise NotImplementedError

    def extra_buttons(self):
        """도구별 추가 버튼 [(글자, 함수), ...]"""
        return []

    # ---------- 화면 구성 ----------
    def _build(self):
        head = tk.Frame(self.root, bg="#1f3347")
        head.pack(fill="x")
        tk.Label(head, text=self.TITLE, fg="white", bg="#1f3347", font=("Malgun Gothic", 18, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(head, text=self.SUBTITLE, fg="#cfd8e3", bg="#1f3347", font=FONT).pack(anchor="w", padx=14, pady=(0, 10))

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        form = ttk.LabelFrame(body, text="입력")
        form.pack(side="left", fill="y", padx=(0, 8))
        for r, (key, label, default, choices) in enumerate(self.fields()):
            ttk.Label(form, text=label, font=FONT).grid(row=r, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=str(default))
            if choices:
                w = ttk.Combobox(form, textvariable=var, values=choices, width=22, state="readonly")
            else:
                w = ttk.Entry(form, textvariable=var, width=24)
            w.grid(row=r, column=1, padx=6, pady=3)
            self.vars[key] = var
        self.info = tk.Label(form, text="", justify="left", font=FONT, fg="#245", wraplength=330)
        self.info.grid(row=len(self.vars) + 1, column=0, columnspan=2, sticky="w", padx=6, pady=8)

        right = ttk.LabelFrame(body, text="미리보기 (CATIA 생성 전 확인용)")
        right.pack(side="left", fill="both", expand=True)
        self.fig = Figure(figsize=(6, 5), dpi=90)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        vbar = tk.Frame(right)
        vbar.pack()
        for name, view in (("입체", "iso"), ("정면", "front"), ("평면", "top"), ("측면", "side")):
            ttk.Button(vbar, text=name, command=lambda vw=view: self.refresh(vw)).pack(side="left", padx=2, pady=2)

        bar = tk.Frame(self.root)
        bar.pack(fill="x", padx=10)
        for text, cmd in (("미리보기", self.refresh), ("CATIA 연결 확인", self.connect),
                          ("CATIA에서 생성", self.generate), ("설정 저장", self.save_settings),
                          ("설정 불러오기", self.load_settings)) + tuple(self.extra_buttons()):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3, pady=4)
        self.log_box = tk.Text(self.root, height=9, bg="#14202c", fg="#d7e3ee", font=("Consolas", 9))
        self.log_box.pack(fill="both", padx=10, pady=(0, 10))
        self.log("준비 완료. 값을 넣고 [미리보기] → [CATIA 연결 확인] → [CATIA에서 생성] 순서로 누르세요.")
        self.root.after(200, self.refresh)

    # ---------- 공통 동작 ----------
    def log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.root.update_idletasks()

    def values(self):
        v = {}
        for (key, label, default, choices) in self.fields():
            raw = self.vars[key].get().strip()
            if isinstance(default, (int, float)) and not isinstance(default, bool):
                try:
                    v[key] = float(raw)
                except ValueError:
                    raise ValueError(f"'{label}'에는 숫자를 넣어야 합니다 (지금: {raw!r})")
            else:
                v[key] = raw
        return v

    def refresh(self, view="iso"):
        try:
            v = self.values()
            boxes = self.make_boxes(v)
            self.ax.clear()
            if boxes:
                preview.draw_boxes(self.ax, boxes, view)
            self.canvas.draw()
            self.info.config(text=self.info_text(v))
        except Exception as e:
            self.log(f"[확인 필요] {e}")

    def connect(self):
        try:
            self.catia = get_catia(dry_run=self.dry_run)
            self.log("CATIA 연결 성공" + (" (모의 모드)" if self.dry_run else ""))
        except Exception as e:
            self.log(f"[연결 실패] {e}")
            messagebox.showerror("CATIA 연결", str(e))

    def generate(self):
        if self.catia is None:
            self.connect()
            if self.catia is None:
                return
        try:
            v = self.values()
            self.make_boxes(v)                   # 입력값 검사 먼저
            self.log("생성 중... CATIA에서 다른 작업을 하지 마세요.")
            out = self.run_catia(v)
            self.log(f"[완료] 저장 폴더: {out}")
        except Exception as e:
            self.log(f"[오류] {e}")
            self.log(traceback.format_exc(limit=2))

    def save_settings(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({k: var.get() for k, var in self.vars.items()}, f, ensure_ascii=False, indent=2)
            self.log(f"설정 저장: {path}")

    def load_settings(self, path=None):
        path = path or filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for k, val in data.items():
                if k in self.vars:
                    self.vars[k].set(str(val))
            self.log(f"설정 불러오기: {path}")
            self.refresh()

    def mainloop(self):
        self.root.mainloop()
