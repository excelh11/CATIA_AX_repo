"""Open a local approved STEP file in CATIA without saving changes."""
import argparse
from pathlib import Path
from common import catia
p=argparse.ArgumentParser();p.add_argument('file',type=Path);a=p.parse_args()
path=a.file.resolve()
if path.suffix.lower() not in ('.stp','.step') or not path.is_file():
    p.error('provide an existing .stp or .step file')
app=catia();doc=app.Documents.Open(str(path))
print('OPENED:',doc.Name)
print('STEP import complete. No file was saved by this script.')
