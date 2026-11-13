"""Validate data, optionally fetch it with SCP, and apply height to a template copy."""
import argparse, json, math, os, subprocess, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, load_request, catia

def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group()
    g.add_argument('--source',type=Path,default=None)
    g.add_argument('--cloud',help='approved SSH source: user@host:/absolute/path/request.json')
    p.add_argument('--port',type=int,default=22)
    p.add_argument('--identity',type=Path)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    folder=ROOT/'outputs'/run_id
    folder.mkdir(parents=True)
    report={'run_id':run_id,'status':'started','mode':'apply' if a.apply else 'dry_run'}
    try:
        if a.cloud:
            if a.cloud.startswith('-') or not a.cloud.count('@') or ':' not in a.cloud:
                raise ValueError('cloud must be user@host:/absolute/path/request.json')
            if not 1<=a.port<=65535: raise ValueError('port out of range')
            source=folder/'download.json'
            cmd=['scp','-P',str(a.port),'-o','ConnectTimeout=15','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+(Path.home()/'Downloads'/'known_hosts').as_posix()]
            if a.identity: cmd+=['-i',str(a.identity.expanduser().resolve())]
            cmd += [a.cloud,str(source)]
            subprocess.run(cmd,check=True,timeout=120)
            report['source_type']='cloud_scp'
        else:
            source=a.source or ROOT/'data'/'request.json'
            report['source_type']='local_file'
        d,digest=load_request(source)
        report.update(request=d,input_sha256=digest)
        # Snapshot the exact validated bytes. No fallback to old data on download failure.
        (folder/'request.json').write_bytes(source.read_bytes())
        if not a.apply:
            report['status']='validated_only'
            print('DRY RUN OK; CATIA has not been modified.')
        else:
            template=ROOT/'templates'/'CampBlock.CATPart'
            if not template.is_file(): raise FileNotFoundError('Run build_template.py first')
            app=catia()
            # Open an independent copy. Original training template is never opened for editing.
            import shutil
            target=folder/'CampBlock.CATPart'
            shutil.copy2(template,target)
            doc=app.Documents.Open(str(target.resolve()))
            part=doc.Part
            pad=part.MainBody.Shapes.Item('CampPad')
            dimension=pad.FirstLimit.Dimension
            before=float(dimension.Value)
            dimension.ValuateFromString(f"{d['height_mm']}mm")
            part.Update()
            after=float(dimension.Value)
            if not math.isclose(after,d['height_mm'],abs_tol=1e-6,rel_tol=0):
                raise RuntimeError('CATIA readback did not match requested height')
            doc.Save()
            report.update(status='saved_and_readback_verified',before_mm=before,
                          after_mm=after,output=str(target))
            # Leave the output visible for instructor/student inspection.
            try: app.ActiveWindow.ActiveViewer.Reframe()
            except Exception: pass
            print('CATIA SAVED:',target)
        print(json.dumps(report,indent=2))
    except Exception as e:
        report.update(status='failed',error_type=type(e).__name__,error=str(e))
        print('FAILED:',type(e).__name__,str(e))
        raise
    finally:
        (folder/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print('REPORT:',folder/'report.json')

if __name__=='__main__': main()
