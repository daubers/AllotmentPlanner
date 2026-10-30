import json, sys, urllib.request
exec(open("demo_seed.py").read().split("password = secrets")[0])  # reuse call()
d = json.load(open("demo.json")); tok = d["token"]; pid = d["allotment"]; ids = d["features"]
P = f"/allotments/{pid}/packets"
packets = {}
for name, var, sup, cal in [
    ("Carrot", "Nantes 2", "Sample Seeds", dict(sow_outdoors=[3,4,5,6,7], harvest=[7,8,9,10])),
    ("Tomato", "Gardener's Delight", "Sample Seeds", dict(sow_indoors=[2,3,4], plant_out=[5,6], harvest=[7,8,9])),
    ("Lettuce", "Little Gem", "Sample Seeds", dict(sow_indoors=[3,4], sow_outdoors=[4,5,6,7,8], harvest=[5,6,7,8,9,10])),
    ("Broad bean", "Aquadulce", "Sample Seeds", dict(sow_outdoors=[10,11,2,3], harvest=[5,6,7])),
    ("Parsley", "Moss Curled", "Sample Seeds", dict(sow_indoors=[2,3], sow_outdoors=[4,5,6,7], harvest=[6,7,8,9,10,11])),
]:
    p = call("POST", P, {"name": name, "variety": var, "supplier": sup, "calendar": cal, "stock": "full"}, tok)
    packets[name] = p["id"]
T = f"/allotments/{pid}/trays"
tray = call("POST", T, {"name": "Greenhouse tray 1", "rows": 4, "cols": 6, "tray_type": "24-cell", "location": "Greenhouse"}, tok)
tid = tray["id"]
def cells(cs, **change):
    call("PATCH", f"{T}/{tid}/cells", {"cells": [{"row": r, "col": c} for r, c in cs], "set": change}, tok)
cells([(0, c) for c in range(6)], status="sown", packet_id=packets["Tomato"], count=1)
cells([(1, c) for c in range(6)], status="sown", packet_id=packets["Lettuce"], count=2)
cells([(2, c) for c in range(4)], status="sown", packet_id=packets["Parsley"], count=3)
cells([(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)], status="germinated")
cells([(0, 5)], status="failed")
print("packets", packets, "tray", tid)
