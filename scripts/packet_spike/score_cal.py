import json, sys
sys.path.insert(0, sys.argv[1] + "/scripts")
from labels import CAL, TEXT_CAL
res = json.load(open(sys.argv[1] + "/out/calread_all.json"))
exact = cells = wrong = 0
found = 0
for k, truth in CAL.items():
    r = next((v for kk, v in res.items() if kk.endswith(k)), None)
    if not r: print(k, "NOT FOUND"); continue
    found += 1
    rot, d = r
    pk = True
    for act, want in truth.items():
        got = set(d["months"].get(act, []))
        want = set(want)
        cells += 12; diff = got ^ want; wrong += len(diff)
        if diff: pk = False; print(f"  {k} rot{rot} {act}: got {sorted(got)} want {sorted(want)}")
    exact += pk
print(f"graphics found {found}/{len(CAL)}; packets exactly right {exact}/{len(CAL)}; month-cells right {cells-wrong}/{cells} ({100*(cells-wrong)/cells:.1f}%)")
print("no graphic (correctly not found):", [k for k in TEXT_CAL if not next((v for kk, v in res.items() if kk.endswith(k) and v), None)])
