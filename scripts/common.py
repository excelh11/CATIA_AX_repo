import hashlib, json, math, os, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load_request(path):
    raw=Path(path).read_bytes()
    if len(raw)>16384: raise ValueError('request is too large')
    d=json.loads(raw.decode('utf-8-sig'))
    required={'schema_version','case_id','revision','unit','height_mm','data_origin'}
    if not isinstance(d,dict) or set(d)!=required:
        raise ValueError('JSON keys do not match the training schema')
    if type(d['schema_version']) is not int or d['schema_version']!=1:
        raise ValueError('schema_version must be 1')
    if d['case_id']!='DEMO01' or d['data_origin']!='synthetic_training':
        raise ValueError('use DEMO01 synthetic training data')
    if d['unit']!='mm': raise ValueError('unit must be mm')
    if not isinstance(d['revision'],str) or not re.fullmatch(r'[A-Za-z0-9]{1,16}',d['revision']):
        raise ValueError('revision must be 1-16 ASCII letters or digits')
    h=d['height_mm']
    if type(h) not in (int,float) or not math.isfinite(h) or not 10<=h<=100:
        raise ValueError('height_mm must be a finite number from 10 to 100')
    return d,hashlib.sha256(raw).hexdigest()
def catia():
    import sys
    if sys.platform!='win32':
        raise RuntimeError('CATIA connection requires Windows desktop Python')
    import win32com.client
    app=win32com.client.GetActiveObject('CATIA.Application')
    app.Visible=True
    return app
def load_env(path=None):
    """C:\\CATIA_AX\\.env 를 읽어 {이름: 값} 으로 돌려준다. 파일이 없으면 빈 dict.
    접속 정보(호스트·포트·PEM 경로)는 코드에 적지 않고 .env 에만 둔다 (.env 는 git 에 올리지 않는다)."""
    p=Path(path) if path else ROOT/'.env'
    env={}
    if p.is_file():
        for line in p.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1)
            env[k.strip()]=os.path.expandvars(v.strip().strip('"').strip("'"))
    return env
