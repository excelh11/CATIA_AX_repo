"""Step 24 -- STP + block height -> cloud GPU analysis -> CATIA assembly + drawing.

Complete automation: upload STP to cloud, run GPU analysis remotely,
download results, change CampBlock height, build assembly + drawing.

Usage (CMD):
    cd C:\\CATIA_AX
    python scripts\\run_full.py --height 60
    (접속 정보는 C:\\CATIA_AX\\.env 에서 읽는다.  --cloud / --port / --identity / --step 을 주면 그 값이 우선)
"""
import argparse, json, math, os, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, load_request, catia, load_env


def _ssh_opts(port, identity):
    opts = ['-p', str(port), '-o', 'ConnectTimeout=15',
            '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + (Path.home() / 'Downloads' / 'known_hosts').as_posix()]
    if identity:
        opts += ['-i', str(identity.expanduser().resolve())]
    return opts


def scp_download(remote_path, local_path, port, identity):
    cmd = ['scp'] + ['-P', str(port)] + ['-o', 'ConnectTimeout=15',
           '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + (Path.home() / 'Downloads' / 'known_hosts').as_posix()]
    if identity:
        cmd += ['-i', str(identity.expanduser().resolve())]
    cmd += [remote_path, str(local_path)]
    fname = remote_path.rsplit('/', 1)[-1] if '/' in remote_path else remote_path
    print(f'  SCP download: {fname} ...', end=' ', flush=True)
    subprocess.run(cmd, check=True, timeout=120)
    print('OK')


def scp_upload(local_path, remote_path, port, identity):
    cmd = ['scp'] + ['-P', str(port)] + ['-o', 'ConnectTimeout=15',
           '-o', 'StrictHostKeyChecking=accept-new', '-o', 'UserKnownHostsFile=' + (Path.home() / 'Downloads' / 'known_hosts').as_posix()]
    if identity:
        cmd += ['-i', str(identity.expanduser().resolve())]
    cmd += [str(local_path), remote_path]
    fname = Path(local_path).name
    print(f'  SCP upload: {fname} ...', end=' ', flush=True)
    subprocess.run(cmd, check=True, timeout=300)
    print('OK')


def ssh_run(user_host, command, port, identity, timeout=300):
    cmd = ['ssh'] + _ssh_opts(port, identity) + [user_host, command]
    print(f'  SSH: {command[:70]}...', flush=True)
    result = subprocess.run(cmd, check=True, timeout=timeout,
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    out = result.stdout or ''
    if out.strip():
        for line in out.strip().split('\n'):
            print(f'    {line}')
    return out


def main():
    p = argparse.ArgumentParser(
        description='STP + height -> cloud GPU -> CATIA assembly + drawing')
    env = load_env()                       # C:\CATIA_AX\.env (없으면 빈 dict)
    default_cloud = (f"{env['ELICE_USER']}@{env['ELICE_HOST']}"
                     if env.get('ELICE_USER') and env.get('ELICE_HOST') else None)
    p.add_argument('--cloud', default=default_cloud,
                   help='user@host (기본: .env 의 ELICE_USER@ELICE_HOST)')
    p.add_argument('--port', type=int, default=int(env.get('ELICE_PORT', 22)))
    p.add_argument('--identity', type=Path,
                   default=Path(env['ELICE_PEM']) if env.get('ELICE_PEM') else None)
    p.add_argument('--step', type=Path,
                   default=ROOT / env.get('STEP_FILE', 'code/data/deid/LPM_OPENER_deid.stp'),
                   help='local STEP file path')
    p.add_argument('--height', type=float, required=True,
                   help='CampBlock height (mm), 10~100')
    p.add_argument('--revision', default='R01')
    a = p.parse_args()

    if not a.cloud:
        p.error('접속 정보가 없습니다: C:\\CATIA_AX\\.env 에 ELICE_USER / ELICE_HOST 를 적거나 --cloud 를 주세요')
    if not 10 <= a.height <= 100:
        p.error('--height must be between 10 and 100 mm')

    step_path = Path(a.step).resolve()
    if not step_path.is_file():
        raise FileNotFoundError(f'STEP file not found: {step_path}')

    stem = step_path.stem
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    folder = ROOT / 'outputs' / run_id
    folder.mkdir(parents=True)
    report = {'run_id': run_id, 'status': 'started', 'mode': 'full_e2e'}

    user_host = a.cloud.rstrip('/')
    remote_code = '~/code'
    remote_deid = f'{remote_code}/data/deid'
    remote_out = f'{remote_code}/data/out'

    try:
        # == 1/6: Upload STP to cloud ==
        print('=' * 60)
        print('  [1/6] STP upload to cloud')
        print('=' * 60)
        scp_upload(step_path, f'{user_host}:{remote_deid}/{step_path.name}',
                   a.port, a.identity)
        report['uploaded_step'] = step_path.name

        # == 2/6: Cloud GPU analysis (step_inspect.py) ==
        print('\n' + '=' * 60)
        print('  [2/6] Cloud GPU analysis (step_inspect.py)')
        print('=' * 60)
        ssh_run(user_host,
                f'cd {remote_code} && python3 day1/step_inspect.py data/deid/{step_path.name}',
                a.port, a.identity, timeout=600)
        report['cloud_inspect'] = 'completed'

        # == 3/6: Cloud design params (make_params.py + make_request.py) ==
        print('\n' + '=' * 60)
        print('  [3/6] Cloud design params generation')
        print('=' * 60)
        ssh_run(user_host,
                f'cd {remote_code} && python3 day1/make_params.py '
                f'--summary data/out/{stem}_summary.json',
                a.port, a.identity)
        ssh_run(user_host,
                f'cd {remote_code} && python3 make_request.py '
                f'--height {a.height} --revision {a.revision} '
                f'--out data/out/request.json',
                a.port, a.identity)
        report['cloud_params'] = 'completed'

        # == 4/6: Download 3 result JSONs ==
        print('\n' + '=' * 60)
        print('  [4/6] Download result JSONs')
        print('=' * 60)
        downloads = {
            'request.json': f'{user_host}:{remote_out}/request.json',
            'design_params.json': f'{user_host}:{remote_out}/design_params.json',
            f'{stem}_summary.json': f'{user_host}:{remote_out}/{stem}_summary.json',
        }
        for local_name, remote in downloads.items():
            scp_download(remote, folder / local_name, a.port, a.identity)
        report['downloaded_files'] = list(downloads.keys())

        # == 5/6: CampBlock height change ==
        print('\n' + '=' * 60)
        print('  [5/6] CampBlock height change')
        print('=' * 60)
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
        pad = part.MainBody.Shapes.Item('CampPad')
        dimension = pad.FirstLimit.Dimension
        before = float(dimension.Value)
        dimension.ValuateFromString(f"{d['height_mm']}mm")
        part.Update()
        after = float(dimension.Value)
        if not math.isclose(after, d['height_mm'], abs_tol=1e-6, rel_tol=0):
            raise RuntimeError('CATIA readback did not match requested height')
        doc.Save()
        print(f'  CampBlock: {before}mm -> {after}mm  [OK]')
        report.update(before_mm=before, after_mm=after, campblock=str(target))

        # == 6/6: efem_cell.py -> assembly + drawing ==
        print('\n' + '=' * 60)
        print('  [6/6] EFEM CELL assembly + drawing')
        print('=' * 60)
        efem_cmd = [
            sys.executable,
            str(ROOT / 'code' / 'day3' / 'efem_cell.py'),
            '--params', str(folder / 'design_params.json'),
            '--step', str(step_path),
            '--summary', str(folder / f'{stem}_summary.json'),
            '--out', str(folder),
        ]
        print(f'  Run: efem_cell.py')
        result = subprocess.run(efem_cmd, cwd=str(ROOT / 'code'), timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f'efem_cell.py failed (exit code {result.returncode})')
        report['efem_cell'] = 'completed'

        # == Done ==
        print('\n' + '=' * 60)
        print('  DONE')
        print('=' * 60)
        report['status'] = 'full_pipeline_completed'
        report['output_folder'] = str(folder)
        print(f'  CampBlock: {before}mm -> {after}mm')
        print(f'  Assembly + drawing generated')
        print(f'  Output: {folder}')

    except Exception as e:
        report.update(status='failed', error_type=type(e).__name__, error=str(e))
        print(f'FAILED: {type(e).__name__} {e}')
        raise
    finally:
        (folder / 'report.json').write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'REPORT: {folder / "report.json"}')


if __name__ == '__main__':
    main()
