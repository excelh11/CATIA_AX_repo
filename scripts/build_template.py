"""Instructor preflight only: creates a new 100 x 80 x 30 mm training block."""
from common import ROOT, catia
out=ROOT/'templates'/'CampBlock.CATPart'
if out.exists(): raise SystemExit('Template already exists; keep it or rename it before rebuilding.')
app=catia()
doc=app.Documents.Add('Part')
part=doc.Part
body=part.MainBody
part.InWorkObject=body
plane=part.OriginElements.PlaneXY
sketch=body.Sketches.Add(plane)
f=sketch.OpenEdition()
f.CreateLine(0.0,0.0,100.0,0.0)
f.CreateLine(100.0,0.0,100.0,80.0)
f.CreateLine(100.0,80.0,0.0,80.0)
f.CreateLine(0.0,80.0,0.0,0.0)
sketch.CloseEdition()
part.Update()
part.InWorkObject=body
pad=part.ShapeFactory.AddNewPad(sketch,30.0)
pad.Name='CampPad'
part.Update()
out.parent.mkdir(parents=True,exist_ok=True)
doc.SaveAs(str(out))
print('TEMPLATE:',out)
print('HEIGHT_MM:',pad.FirstLimit.Dimension.Value)
doc.Close()
