from common import ROOT, load_request

data, digest = load_request(ROOT / "data" / "request.json")
height_mm = data["height_mm"]
catia_input = f"{height_mm}mm"
print("revision:", data["revision"])
print("height_mm:", height_mm)
print("CATIA input:", catia_input)
print("SHA256:", digest)
