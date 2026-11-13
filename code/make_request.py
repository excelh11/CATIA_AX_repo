"""Run on the cloud: create synthetic training dimensions, not EFEM measurements."""
import argparse, json, math, os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--height', type=float, default=30.0)
p.add_argument('--revision', default='R01')
p.add_argument('--out', default='request.json')
a=p.parse_args()
if not math.isfinite(a.height) or not 10 <= a.height <= 100:
    p.error('height must be a finite number between 10 and 100 mm')
if not a.revision.isascii() or not a.revision.isalnum() or len(a.revision)>16:
    p.error('revision must be 1-16 ASCII letters or digits')
data={'schema_version':1,'case_id':'DEMO01','revision':a.revision,
      'unit':'mm','height_mm':a.height,'data_origin':'synthetic_training'}
out=Path(a.out).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
tmp=out.with_suffix(out.suffix+'.tmp')
tmp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
os.replace(tmp,out)
print(out)
print(json.dumps(data,indent=2))
