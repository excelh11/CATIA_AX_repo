"""Read-only ZIP inventory. Does not claim geometry validation or anonymization."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('zip_file',type=Path);p.add_argument('--out',type=Path,default=Path('efem_inventory.json'));a=p.parse_args()
rows=[]
with zipfile.ZipFile(a.zip_file) as z:
    for info in z.infolist():
        if info.is_dir(): continue
        digest=hashlib.sha256(); products=0; schema=None; header=b''
        with z.open(info) as f:
            for line in f:
                digest.update(line)
                products+=bool(re.match(rb'\s*#\d+\s*=\s*PRODUCT\s*\(',line))
                if len(header)<16384: header+=line
        m=re.search(rb"FILE_SCHEMA\s*\(\((.*?)\)\)",header,re.S)
        if m: schema=m.group(1).decode('ascii','replace')
        rows.append({'file':info.filename,'size_bytes':info.file_size,
                     'sha256':digest.hexdigest(),'product_entity_count':products,
                     'schema':schema,'step_header_found':header.startswith(b'ISO-10303-21;')})
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
