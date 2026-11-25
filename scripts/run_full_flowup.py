"""Step 24 (AWS 서버 판) -- STP + 블록 높이 -> AWS 클라우드 분석 -> CATIA 조립 + 도면.

run_full.py 와 하는 일은 같고(+ 7단계 프레임 부품별 도면 일괄), 클라우드와 연결하는 방법만 다르다.
  run_full.py        : SSH / SCP (엘리스)
  run_full_flowup.py : HTTPS 미리보기 포트 (AWS 서버 — SSH 가 막혀 있음)

준비:
  1) AWS 터미널에서  python ~/code/flowup_server.py --port 10010  을 띄워 둔다
  2) C:\\CATIA_AX\\.env 에 아래 두 줄
       FLOWUP_URL=https://p10010-u31364-i4.flowup.ai.kr     (강의실 [실습환경] 의 미리보기 주소)
       FLOWUP_TOKEN=서버가_보여준_토큰

사용 (CMD, CATIA V5 켠 상태):
    cd C:\\CATIA_AX
    python scripts\\run_full_flowup.py --height 60
    python scripts\\run_full_flowup.py --height 60 --cloud-only     (CATIA 없이 1~4단계만 시험)
"""
import argparse, hashlib, json, math, subprocess, sys, time, uuid
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, load_request, catia, load_env

UA = 'CATIA-AX-FlowUP/1.0'


class Cloud:
    """AWS 접수 창구(flowup_server.py)와 대화하는 작은 도우미."""

    def __init__(self, url, token):
        self.url, self.token = url.rstrip('/'), token

    def call(self, method, path, params=None, data=None, timeout=120, tries=4, raw=False):
        q = ('?' + urllib.parse.urlencode(params)) if params else ''
        last = None
        for n in range(1, tries + 1):
            req = urllib.request.Request(self.url + path + q, data=data, method=method,
                                         headers={'X-Token': self.token, 'User-Agent': UA,
                                                  'Content-Type': 'application/octet-stream'})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read()
                    if raw:
                        return body
                    if 'json' not in (r.headers.get('Content-Type') or ''):
                        raise RuntimeError('JSON 이 아닌 응답 — 미리보기 주소가 맞는지, '
                                           'AWS 터미널에서 flowup_server.py 가 켜져 있는지 확인하세요')
                    return json.loads(body.decode('utf-8'))
            except urllib.error.HTTPError as e:
                text = e.read().decode('utf-8', 'replace')
                try:
                    msg = json.loads(text).get('error', text)
                except ValueError:
                    msg = text[:200]
                if e.code == 413:
                    raise RuntimeError('조각이 너무 큽니다 (HTTP 413) — --chunk-mb 1 처럼 줄여서 다시 실행하세요') from None
                if e.code in (401, 400, 404, 409):          # 다시 해도 같은 결과 → 바로 알림
                    raise RuntimeError(f'{method} {path} → HTTP {e.code}: {msg}') from None
                last = f'HTTP {e.code}: {msg}'
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = str(getattr(e, 'reason', e))
            if n < tries:
                time.sleep(2 * n)
        raise RuntimeError(f'{method} {path} 실패 ({tries}번 시도): {last}')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def upload(cloud, step_path, chunk_mb):
    name, size, digest = step_path.name, step_path.stat().st_size, sha256_file(step_path)
    st = cloud.call('GET', '/stat', {'name': name})
    if st.get('exists') and st.get('sha256') == digest:
        print(f'  {name}: 서버에 같은 파일이 이미 있음 → 올리기 생략')
        return
    chunk = max(1, int(chunk_mb * 1024 * 1024))
    sent, t0 = 0, time.time()
    with open(step_path, 'rb') as f:
        while sent < size:
            f.seek(sent)
            data = f.read(chunk)
            r = cloud.call('PUT', '/upload', {'name': name, 'offset': sent}, data=data)
            sent = r['size']
            print(f'\r  올리는 중 {sent / size * 100:5.1f}%  ({sent // 1048576}/{size // 1048576} MB)',
                  end='', flush=True)
    print(f'  {time.time() - t0:.0f}초')
    cloud.call('POST', '/upload/finish', {'name': name, 'size': size, 'sha256': digest}, data=b'')
    print(f'  업로드 확인: 크기·SHA-256 일치')


def run_cloud(cloud, name, height, revision, limit_sec):
    cloud.call('POST', '/run', {'name': name, 'height': height, 'revision': revision}, data=b'')
    seen, t0 = 0, time.time()
    while True:
        st = cloud.call('GET', '/status', {'since': seen})
        for line in st['log']:
            print(f'    {line}')
        seen = st['total']
        if st['state'] == 'done':
            return
        if st['state'] == 'failed':
            raise RuntimeError(f"클라우드 분석 실패: {st.get('error')}")
        if time.time() - t0 > limit_sec:
            raise TimeoutError(f'클라우드 분석이 {limit_sec}초 안에 끝나지 않았습니다')
        time.sleep(3)


def main():
    env = load_env()
    p = argparse.ArgumentParser(description='STP + height -> AWS cloud -> CATIA assembly + drawing')
    p.add_argument('--url', default=env.get('FLOWUP_URL'), help='미리보기 주소 (기본: .env 의 FLOWUP_URL)')
    p.add_argument('--token', default=env.get('FLOWUP_TOKEN'), help='접속 토큰 (기본: .env 의 FLOWUP_TOKEN)')
    p.add_argument('--step', type=Path, default=ROOT / env.get('STEP_FILE', 'code/data/deid/LPM_OPENER_deid.stp'))
    p.add_argument('--height', type=float, required=True, help='CampBlock height (mm), 10~100')
    p.add_argument('--revision', default='R01')
    p.add_argument('--chunk-mb', type=float, default=4.0, help='한 번에 올릴 조각 크기(MB)')
    p.add_argument('--cloud-only', action='store_true', help='CATIA 단계(5~7) 없이 클라우드만 시험')
    p.add_argument('--no-batch-drawings', action='store_true', help='7단계(프레임 부품별 도면 일괄) 건너뛰기')
    a = p.parse_args()

    if not a.url or not a.token:
        p.error('접속 정보가 없습니다: C:\\CATIA_AX\\.env 에 FLOWUP_URL / FLOWUP_TOKEN 을 적거나 --url / --token 을 주세요')
    if not 10 <= a.height <= 100:
        p.error('--height must be between 10 and 100 mm')
    step_path = Path(a.step).resolve()
    if not step_path.is_file():
        raise FileNotFoundError(f'STEP file not found: {step_path}')
    if not step_path.name.endswith('_deid.stp'):
        p.error('비식별 파일(..._deid.stp)만 클라우드에 올릴 수 있습니다')

    stem = step_path.stem
    cloud = Cloud(a.url, a.token)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    folder = ROOT / 'outputs' / run_id
    folder.mkdir(parents=True)
    report = {'run_id': run_id, 'status': 'started', 'mode': 'full_e2e_flowup', 'cloud_url': cloud.url}

    def banner(t):
        print('\n' + '=' * 60 + f'\n  {t}\n' + '=' * 60, flush=True)

    try:
        banner('[0/7] AWS 접수 창구 연결 확인')
        info = cloud.call('GET', '/ping')
        print(f"  Python {info['python']} · OCP {'OK' if info['ocp'] else '없음!'} · {info['code']}")
        if not info['ocp']:
            raise RuntimeError('AWS 서버에서 OCP 를 불러오지 못합니다 (venv 를 켜고 flowup_server.py 를 실행했는지 확인)')

        banner('[1/7] STP upload to cloud')
        upload(cloud, step_path, a.chunk_mb)
        report['uploaded_step'] = step_path.name

        banner('[2~3/7] Cloud analysis (step_inspect · make_params · make_request)')
        run_cloud(cloud, step_path.name, a.height, a.revision, limit_sec=1200)
        report['cloud_inspect'] = report['cloud_params'] = 'completed'

        banner('[4/7] Download result JSONs')
        names = ['request.json', 'design_params.json', f'{stem}_summary.json']
        for n in names:
            (folder / n).write_bytes(cloud.call('GET', '/out', {'name': n}, raw=True))
            print(f'  {n} ... OK')
        report['downloaded_files'] = names
        dp = json.loads((folder / 'design_params.json').read_text(encoding='utf-8'))
        print(f"  확인: FFU Y = {dp['ffu']['Y']} · frame {dp['frame3030']['W']}x{dp['frame3030']['D']}x{dp['frame3030']['H']}")

        if a.cloud_only:
            report['status'] = 'cloud_only_completed'
            report['output_folder'] = str(folder)
            banner('DONE (cloud only)')
            print(f'  Output: {folder}')
            return

        banner('[5/7] CampBlock height change')
        d, digest = load_request(folder / 'request.json')
        report.update(request=d, input_sha256=digest)
        template = ROOT / 'templates' / 'CampBlock.CATPart'
        if not template.is_file():
            raise FileNotFoundError('Run build_template.py first')
        app = catia()
        import shutil
        target = folder / 'CampBlock.CATPart'
        shutil.copy2(template, target)
        doc = app.Documents.Open(str(target.resolve()))
        part = doc.Part
        dimension = part.MainBody.Shapes.Item('CampPad').FirstLimit.Dimension
        before = float(dimension.Value)
        dimension.ValuateFromString(f"{d['height_mm']}mm")
        part.Update()
        after = float(dimension.Value)
        if not math.isclose(after, d['height_mm'], abs_tol=1e-6, rel_tol=0):
            raise RuntimeError('CATIA readback did not match requested height')
        doc.Save()
        print(f'  CampBlock: {before}mm -> {after}mm  [OK]')
        report.update(before_mm=before, after_mm=after, campblock=str(target))

        banner('[6/7] EFEM CELL assembly + drawing')
        efem_cmd = [sys.executable, str(ROOT / 'code' / 'day3' / 'efem_cell.py'),
                    '--params', str(folder / 'design_params.json'),
                    '--step', str(step_path),
                    '--summary', str(folder / f'{stem}_summary.json'),
                    '--out', str(folder)]
        result = subprocess.run(efem_cmd, cwd=str(ROOT / 'code'), timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f'efem_cell.py failed (exit code {result.returncode})')
        report['efem_cell'] = 'completed'

        if not a.no_batch_drawings:
            banner('[7/7] Batch drawings — 프레임 부품 전부 (README ③ 폴더 일괄 생성)')
            frame_dirs = sorted(str(p) for p in folder.glob('*_FRAME3030_*') if p.is_dir())
            if not frame_dirs:
                raise RuntimeError(f'프레임 폴더(*_FRAME3030_*)를 찾지 못했습니다: {folder}')
            batch_cmd = [sys.executable, str(ROOT / 'code' / 'day3' / 'batch_drawings.py'), *frame_dirs]
            result = subprocess.run(batch_cmd, cwd=str(ROOT / 'code'), timeout=1800)
            if result.returncode != 0:
                raise RuntimeError(f'batch_drawings.py failed (exit code {result.returncode})')
            report['batch_drawings'] = frame_dirs

        banner('DONE')
        report['status'] = 'full_pipeline_completed'
        report['output_folder'] = str(folder)
        print(f'  CampBlock: {before}mm -> {after}mm')
        print('  Assembly + drawing generated' + ('' if a.no_batch_drawings else ' + 부품별 도면 일괄'))
        print(f'  Output: {folder}')

    except Exception as e:
        report.update(status='failed', error_type=type(e).__name__, error=str(e))
        print(f'\nFAILED: {type(e).__name__} {e}')
        raise
    finally:
        (folder / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'REPORT: {folder / "report.json"}')


if __name__ == '__main__':
    main()
