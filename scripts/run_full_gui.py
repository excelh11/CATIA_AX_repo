"""Step 24 GUI -- EFEM CELL end-to-end automation.

STP file + block height input -> cloud GPU analysis -> CATIA assembly + drawing.
Internally calls scripts/run_full.py as a subprocess.

Usage (CMD):
    cd C:\\CATIA_AX
    python scripts\\run_full_gui.py
"""
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

from common import load_env   # 같은 scripts 폴더의 common.py

ROOT = Path(__file__).resolve().parents[1]
ENV = load_env()                    # C:\CATIA_AX\.env — 접속 정보는 여기에서만 읽는다

FONT = ("Malgun Gothic", 10)
FONT_B = ("Malgun Gothic", 10, "bold")
LOG_FONT = ("Consolas", 10)
HDR_BG = "#1a365d"


class AutomationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EFEM CELL 완전 자동화")
        self.root.geometry("820x780")
        self.running = False
        self.result_folder = None
        self._build()

    def _build(self):
        # -- Header --
        hdr = tk.Frame(self.root, bg=HDR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="EFEM CELL 완전 자동화", fg="white", bg=HDR_BG,
                 font=("Malgun Gothic", 16, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(hdr, text="STP 업로드 -> 클라우드 GPU 분석 -> CampBlock -> 프레임 + FFU -> 조립품 + 도면",
                 fg="#93b5e0", bg=HDR_BG, font=FONT).pack(anchor="w", padx=14, pady=(0, 10))

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        # -- Design input --
        design = ttk.LabelFrame(body, text="설계 입력")
        design.pack(fill="x", pady=(0, 6))

        ttk.Label(design, text="STEP 파일:", font=FONT).grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.step_var = tk.StringVar(
            value=str(ROOT / ENV.get("STEP_FILE", "code/data/deid/LPM_OPENER_deid.stp")))
        ttk.Entry(design, textvariable=self.step_var, width=54).grid(row=0, column=1, sticky="w", padx=6, pady=3)
        ttk.Button(design, text="찾기...", command=self._pick_step, width=6).grid(row=0, column=2, padx=4)

        self.height_var = self._row(design, 1, "블록 높이 (mm):", "60.0", 10)
        self.rev_var = self._row(design, 2, "리비전:", "R01", 10)

        # -- Cloud connection --
        cloud = ttk.LabelFrame(body, text="클라우드 접속 정보  (엘리스 대시보드에서 확인)")
        cloud.pack(fill="x", pady=(0, 6))

        self.host_var = self._row(cloud, 0, "호스트:", ENV.get("ELICE_HOST", ""), 40)
        self.port_var = self._row(cloud, 1, "포트:", ENV.get("ELICE_PORT", ""), 10)
        self.user_var = self._row(cloud, 2, "사용자:", ENV.get("ELICE_USER", "elicer"), 16)

        ttk.Label(cloud, text="PEM 키 파일:", font=FONT).grid(row=3, column=0, sticky="w", padx=6, pady=3)
        self.pem_var = tk.StringVar(value=ENV.get("ELICE_PEM", str(Path.home() / "Downloads" / "my-elice.pem")))
        ttk.Entry(cloud, textvariable=self.pem_var, width=44).grid(row=3, column=1, sticky="w", padx=6, pady=3)
        ttk.Button(cloud, text="찾기...", command=self._pick_pem, width=6).grid(row=3, column=2, padx=4)

        # -- Buttons --
        btns = tk.Frame(body)
        btns.pack(fill="x", pady=6)
        self.run_btn = tk.Button(
            btns, text="자동화 실행", font=("Malgun Gothic", 13, "bold"),
            bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white",
            relief="flat", cursor="hand2", command=self.run_pipeline)
        self.run_btn.pack(fill="x", ipady=5)

        sub = tk.Frame(btns)
        sub.pack(fill="x", pady=(4, 0))
        self.folder_btn = ttk.Button(sub, text="결과 폴더 열기", command=self._open_folder, state="disabled")
        self.folder_btn.pack(side="left")
        ttk.Button(sub, text="로그 지우기", command=self._clear_log).pack(side="right")

        # -- Log area --
        lf = ttk.LabelFrame(body, text="실행 로그")
        lf.pack(fill="both", expand=True)
        self.log_box = tk.Text(lf, bg="#0f172a", fg="#e2e8f0", font=LOG_FONT,
                               wrap="word", state="disabled", height=14)
        sb = ttk.Scrollbar(lf, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)

        self.log_box.tag_configure("info", foreground="#93c5fd")
        self.log_box.tag_configure("ok", foreground="#86efac")
        self.log_box.tag_configure("err", foreground="#fca5a5")
        self.log_box.tag_configure("head", foreground="#fbbf24", font=("Consolas", 10, "bold"))

        self._log("준비 완료.", "info")
        self._log("1) STEP 파일과 블록 높이를 입력하세요.", "info")
        self._log("2) 클라우드 접속 정보를 확인하세요.", "info")
        self._log("3) [자동화 실행] 을 누르면 클라우드 분석부터 도면까지 자동 완성됩니다.", "info")

    # -- Helpers --
    def _row(self, parent, r, label, default, width):
        ttk.Label(parent, text=label, font=FONT).grid(row=r, column=0, sticky="w", padx=6, pady=3)
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=r, column=1, sticky="w", padx=6, pady=3)
        return var

    def _pick_pem(self):
        p = filedialog.askopenfilename(
            title="PEM 키 파일 선택",
            filetypes=[("PEM", "*.pem"), ("모든 파일", "*.*")])
        if p:
            self.pem_var.set(p)

    def _pick_step(self):
        p = filedialog.askopenfilename(
            title="STEP 파일 선택",
            filetypes=[("STEP", "*.stp;*.step"), ("모든 파일", "*.*")])
        if p:
            self.step_var.set(p)

    def _open_folder(self):
        if self.result_folder and os.path.isdir(self.result_folder):
            os.startfile(self.result_folder)

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _log(self, msg, tag="info"):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.root.update_idletasks()

    def _log_safe(self, msg, tag="info"):
        self.root.after(0, self._log, msg, tag)

    # -- Pipeline --
    def run_pipeline(self):
        if self.running:
            return

        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        user = self.user_var.get().strip()
        pem = self.pem_var.get().strip()
        step = self.step_var.get().strip()
        height = self.height_var.get().strip()
        rev = self.rev_var.get().strip()

        if not host or not port or not user:
            self._log("[입력 오류] 호스트, 포트, 사용자를 모두 입력하세요. (C:\\CATIA_AX\\.env 에 적어 두면 자동으로 채워집니다)", "err")
            return
        try:
            h = float(height)
            if not 10 <= h <= 100:
                raise ValueError
        except ValueError:
            self._log("[입력 오류] 블록 높이는 10~100 사이 숫자여야 합니다.", "err")
            return

        script = ROOT / "scripts" / "run_full.py"
        if not script.is_file():
            self._log(f"[파일 없음] {script}", "err")
            self._log("run_full.py 를 먼저 생성하세요.", "err")
            return

        self.running = True
        self.run_btn.configure(state="disabled", text="실행 중...")
        self.folder_btn.configure(state="disabled")

        cloud = f"{user}@{host}"
        cmd = [sys.executable, str(script),
               "--cloud", cloud, "--port", port,
               "--step", step, "--height", height, "--revision", rev]
        if pem:
            cmd += ["--identity", pem]

        self._log("=" * 52, "head")
        self._log("  End-to-End 파이프라인 시작", "head")
        self._log("=" * 52, "head")
        self._log(f"  Cloud: {cloud}:{port}", "info")
        self._log(f"  STEP:  {Path(step).name}", "info")
        self._log(f"  Height: {height} mm", "info")

        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def _worker(self, cmd):
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(ROOT), env=env)

            for raw in proc.stdout:
                line = raw.rstrip("\n\r")
                if not line:
                    continue
                if "REPORT:" in line:
                    rpath = line.split("REPORT:", 1)[1].strip()
                    folder = str(Path(rpath).parent)
                    self.result_folder = folder
                    self._log_safe(line, "ok")
                    self.root.after(0, lambda: self.folder_btn.configure(state="normal"))
                elif "FAILED" in line or "Error" in line or "Traceback" in line:
                    self._log_safe(line, "err")
                elif "OK" in line or "completed" in line or "DONE" in line:
                    self._log_safe(line, "ok")
                elif line.startswith("===") or any(f"[{i}/6]" in line for i in range(1, 7)):
                    self._log_safe(line, "head")
                else:
                    self._log_safe(line, "info")

            proc.wait()
            if proc.returncode == 0:
                self._log_safe("", "info")
                self._log_safe("End-to-End 파이프라인 완료!", "ok")
            else:
                self._log_safe(f"실행 실패 (exit code {proc.returncode})", "err")

        except Exception as e:
            self._log_safe(f"오류: {e}", "err")
        finally:
            self.root.after(0, self._done)

    def _done(self):
        self.run_btn.configure(state="normal", text="자동화 실행")
        self.running = False

    def mainloop(self):
        self.root.mainloop()


if __name__ == "__main__":
    AutomationGUI().mainloop()
