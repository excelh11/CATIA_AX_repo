"""AWS 실습 서버용 '분석 접수 창구' — SSH 대신 미리보기 포트(HTTPS)로 내 PC 와 연결한다.

AWS 서버는 SSH(22번)가 막혀 있어 run_full.py(scp/ssh) 를 쓸 수 없다.
대신 FlowUP 이 열어 주는 미리보기 포트(예: 10010 → https://p10010-u31364-i4.flowup.ai.kr)에
이 프로그램을 띄워 두면, 내 PC 의 scripts/run_full_flowup.py 가
  STEP 올리기 → 분석 3개(step_inspect · make_params · make_request) → 결과 JSON 내려받기
를 웹으로 처리한다.  (파이썬 표준 라이브러리만 사용)

실행 (AWS 터미널, venv 켠 상태):
    source ~/venv/bin/activate
    python ~/code/flowup_server.py --port 10010
처음 실행하면 접속 토큰(비밀번호)을 만들어 ~/.flowup_token 에 저장하고 화면에 보여 준다.
그 토큰을 내 PC 의 C:\\CATIA_AX\\.env 에 FLOWUP_TOKEN= 으로 적는다.
멈출 때는 Ctrl+C.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CODE = Path(__file__).resolve().parent          # ~/code
DEID = CODE / "data" / "deid"
OUT = CODE / "data" / "out"

STEP_NAME = re.compile(r"[A-Za-z0-9_\-]{1,80}_deid\.stp")          # 비식별 파일만 받는다
OUT_NAME = re.compile(r"(request|design_params|[A-Za-z0-9_\-]{1,80}_deid_(summary|preview))\.(json|png)")
REVISION = re.compile(r"[A-Za-z0-9]{1,16}")
MAX_STEP = 1024 * 1024 * 1024       # 1GB
MAX_CHUNK = 16 * 1024 * 1024        # 한 번에 받는 조각 최대 16MB

TOKEN = ""
LOCK = threading.Lock()
JOB = {"state": "idle", "step": None, "log": [], "started": None, "finished": None, "error": None}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _log(line):
    with LOCK:
        JOB["log"].append(line)
        del JOB["log"][:-400]                  # 최근 400줄만 보관


def _run_job(name, height, revision):
    stem = name[:-4]
    cmds = [
        ("step_inspect", [sys.executable, "day1/step_inspect.py", f"data/deid/{name}"]),
        ("make_params", [sys.executable, "day1/make_params.py", "--summary", f"data/out/{stem}_summary.json"]),
        ("make_request", [sys.executable, "make_request.py", "--height", str(height),
                          "--revision", revision, "--out", "data/out/request.json"]),
    ]
    try:
        # 예전 결과가 남아 있으면 '옛 파일을 받는' 사고가 난다 → 먼저 지운다
        for f in ("request.json", "design_params.json", f"{stem}_summary.json", f"{stem}_preview.png"):
            (OUT / f).unlink(missing_ok=True)
        for step, cmd in cmds:
            with LOCK:
                JOB["step"] = step
            _log(f"$ {' '.join(cmd[1:])}")
            p = subprocess.Popen(cmd, cwd=CODE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                _log(line.rstrip("\n"))
            if p.wait() != 0:
                raise RuntimeError(f"{step} 실패 (exit {p.returncode})")
        with LOCK:
            JOB.update(state="done", step=None, finished=time.time())
        _log("[완료] 분석 3개 끝")
    except Exception as e:                      # noqa: BLE001 — 어떤 실패든 상태로 돌려준다
        with LOCK:
            JOB.update(state="failed", finished=time.time(), error=str(e))
        _log(f"[실패] {e}")


class Handler(BaseHTTPRequestHandler):
    server_version = "CATIA-AX-FlowUP/1.0"

    # ---------- 공통 ----------
    def _send(self, code, obj=None, body=None, ctype="application/json; charset=utf-8"):
        data = body if body is not None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        got = self.headers.get("X-Token", "")
        if TOKEN and hmac.compare_digest(got.encode(), TOKEN.encode()):
            return True
        self._send(401, {"ok": False, "error": "토큰이 없거나 틀립니다 (X-Token)"})
        return False

    def _q(self):
        u = urlparse(self.path)
        return u.path.rstrip("/") or "/", {k: v[0] for k, v in parse_qs(u.query).items()}

    def _body(self, limit):
        n = int(self.headers.get("Content-Length", "0"))
        if n < 0 or n > limit:
            raise ValueError(f"본문 크기 {n} 가 허용치를 넘습니다")
        return self.rfile.read(n)

    def log_message(self, fmt, *args):         # 접속 로그는 한 줄로 짧게
        sys.stderr.write("  [웹] " + (fmt % args) + "\n")

    # ---------- GET ----------
    def do_GET(self):
        path, q = self._q()
        if path == "/":
            # 브라우저로 열었을 때 '살아 있음'만 알려 준다 (토큰 없이 볼 수 있는 유일한 주소)
            return self._send(200, {"ok": True, "service": "CATIA AX AWS 접수 창구",
                                    "hint": "토큰(X-Token)이 있어야 사용할 수 있습니다"})
        if not self._auth():
            return
        if path == "/ping":
            ocp = True
            try:
                import OCP  # noqa: F401
            except Exception:                   # noqa: BLE001
                ocp = False
            return self._send(200, {"ok": True, "python": sys.version.split()[0], "ocp": ocp,
                                    "code": str(CODE), "state": JOB["state"]})
        if path == "/stat":
            name = q.get("name", "")
            if not STEP_NAME.fullmatch(name):
                return self._send(400, {"ok": False, "error": "파일 이름은 ..._deid.stp 형식이어야 합니다"})
            p = DEID / name
            if not p.is_file():
                return self._send(200, {"ok": True, "exists": False})
            return self._send(200, {"ok": True, "exists": True, "size": p.stat().st_size, "sha256": _sha256(p)})
        if path == "/status":
            since = int(q.get("since", "0") or 0)
            with LOCK:
                log = JOB["log"]
                return self._send(200, {"ok": True, "state": JOB["state"], "step": JOB["step"],
                                        "error": JOB["error"], "total": len(log),
                                        "log": log[since:] if since <= len(log) else log})
        if path == "/out":
            name = q.get("name", "")
            if not OUT_NAME.fullmatch(name):
                return self._send(400, {"ok": False, "error": "내려받을 수 없는 파일 이름입니다"})
            p = OUT / name
            if not p.is_file():
                return self._send(404, {"ok": False, "error": f"{name} 이 아직 없습니다"})
            ctype = "image/png" if name.endswith(".png") else "application/json; charset=utf-8"
            return self._send(200, body=p.read_bytes(), ctype=ctype)
        return self._send(404, {"ok": False, "error": "없는 주소"})

    # ---------- PUT: STEP 조각 올리기 ----------
    def do_PUT(self):
        path, q = self._q()
        if not self._auth():
            return
        if path != "/upload":
            return self._send(404, {"ok": False, "error": "없는 주소"})
        name = q.get("name", "")
        if not STEP_NAME.fullmatch(name):
            return self._send(400, {"ok": False, "error": "비식별 파일(..._deid.stp)만 올릴 수 있습니다"})
        try:
            offset = int(q.get("offset", "0"))
            data = self._body(MAX_CHUNK)
        except ValueError as e:
            return self._send(400, {"ok": False, "error": str(e)})
        part = DEID / (name + ".part")
        DEID.mkdir(parents=True, exist_ok=True)
        cur = part.stat().st_size if part.exists() else 0
        if offset > cur or offset + len(data) > MAX_STEP:
            return self._send(409, {"ok": False, "error": "조각 순서가 맞지 않습니다", "size": cur})
        with open(part, "r+b" if part.exists() else "wb") as f:   # 같은 조각을 다시 보내도 안전 (덮어쓰기)
            f.truncate(offset)
            f.seek(offset)
            f.write(data)
        return self._send(200, {"ok": True, "size": offset + len(data)})

    # ---------- POST ----------
    def do_POST(self):
        path, q = self._q()
        if not self._auth():
            return
        if path == "/upload/finish":
            name = q.get("name", "")
            if not STEP_NAME.fullmatch(name):
                return self._send(400, {"ok": False, "error": "파일 이름 오류"})
            part = DEID / (name + ".part")
            if not part.is_file():
                return self._send(404, {"ok": False, "error": "올라온 조각이 없습니다"})
            size, digest = part.stat().st_size, _sha256(part)
            if str(size) != q.get("size") or digest != q.get("sha256"):
                part.unlink()
                return self._send(409, {"ok": False, "error": "크기·해시가 달라 버렸습니다. 다시 올리세요",
                                        "size": size, "sha256": digest})
            part.replace(DEID / name)
            return self._send(200, {"ok": True, "size": size, "sha256": digest})
        if path == "/run":
            name = q.get("name", "")
            revision = q.get("revision", "R01")
            try:
                height = float(q.get("height", ""))
            except ValueError:
                return self._send(400, {"ok": False, "error": "height 는 숫자여야 합니다"})
            if not STEP_NAME.fullmatch(name) or not (DEID / name).is_file():
                return self._send(400, {"ok": False, "error": f"{name} 이 서버에 없습니다"})
            if not 10 <= height <= 100 or not REVISION.fullmatch(revision):
                return self._send(400, {"ok": False, "error": "height 10~100, revision 영문·숫자 1~16자"})
            with LOCK:
                if JOB["state"] == "running":
                    return self._send(409, {"ok": False, "error": "이미 분석 중입니다"})
                JOB.update(state="running", step=None, log=[], started=time.time(), finished=None, error=None)
            threading.Thread(target=_run_job, args=(name, height, revision), daemon=True).start()
            return self._send(202, {"ok": True, "state": "running"})
        return self._send(404, {"ok": False, "error": "없는 주소"})


def main():
    global TOKEN
    ap = argparse.ArgumentParser(description="AWS 분석 접수 창구 (SSH 대신 HTTPS 미리보기 포트)")
    ap.add_argument("--port", type=int, default=10010, help="내 미리보기 포트 (강의실 [실습환경] 화면 참고)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--token-file", type=Path, default=Path.home() / ".flowup_token")
    a = ap.parse_args()

    if a.token_file.is_file():
        TOKEN = a.token_file.read_text(encoding="utf-8").strip()
    if not TOKEN:
        TOKEN = secrets.token_urlsafe(24)
        a.token_file.write_text(TOKEN + "\n", encoding="utf-8")
    os.chmod(a.token_file, 0o600)              # 나만 읽기

    print("=" * 60)
    print("  CATIA AX — AWS 분석 접수 창구")
    print("=" * 60)
    print(f"  포트       : {a.port}")
    print(f"  코드 폴더  : {CODE}")
    print(f"  접속 토큰  : {TOKEN}")
    print("  → 내 PC  C:\\CATIA_AX\\.env 에  FLOWUP_TOKEN=위_토큰  으로 적으세요")
    print("  → 브라우저로 미리보기 주소를 열어 {\"ok\": true ...} 가 보이면 연결 성공")
    print("  멈추기: Ctrl+C")
    print("=" * 60, flush=True)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  종료")


if __name__ == "__main__":
    main()
