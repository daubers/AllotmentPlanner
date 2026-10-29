import json, re, sys
S = sys.argv[1]
sys.path.insert(0, S + "/scripts")
from labels import LABELS
res = json.load(open(S + "/out/" + (sys.argv[2] if len(sys.argv) > 2 else "vlm_tr.json")))
def depth(t):
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s?(mm|cm)\b[^.\n]{0,25}?\bdeep|depth of (\d+(?:\.\d+)?)\s?(mm|cm)|(\d+(?:\.\d+)?)\s?(mm|cm)\s*\(", t, re.I):
        v, u = next((m.group(i), m.group(i + 1)) for i in (1, 3, 5) if m.group(i))
        return round(float(v) * (10 if u.lower() == "cm" else 1), 1)
def germ(t):
    m = re.search(r"(?:appear|germinat\w*|emerge)[^.\d]{0,40}(\d+)\s*(?:-|–|to)\s*(\d+)\s*days", t, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else None
def sowby(t):
    m = re.search(r"sow\s*by\W{0,8}(?:YE\s*)?(?:[A-Z]{3}\s*)?(?:\d{1,2}\s*/\s*)?(20\d\d)", t, re.I)
    return int(m.group(1)) if m else None
def seeds(t):
    m = re.search(r"(?:average|avg)[^\n\d]{0,20}(?:contents?\s*)?(\d[\d,]*)\s*seeds?", t, re.I) or re.search(r"(\d[\d,]*)\s*seeds", t, re.I)
    return int(m.group(1).replace(",", "")) if m else None
tot = {k: [0, 0] for k in ("seeds", "depth", "germinate", "best_before")}
wrong = []
for k, lab in LABELS.items():
    r = next((v for kk, v in res.items() if kk.endswith(k)), None)
    if not r: continue
    t = r["raw"]
    for f, got, want in (("seeds", seeds(t), lab["seeds"]), ("depth", depth(t), lab["depth"]),
                         ("germinate", germ(t), lab["g"]), ("best_before", sowby(t), lab["bb"])):
        ok = (got == want) if want is not None else got is None
        if f == "depth" and want and got: ok = abs(got - want) < 1
        tot[f][1] += 1; tot[f][0] += bool(ok)
        if not ok: wrong.append((k, f, got, want))
print(f"{len(res)} packets mean {sum(v['seconds'] for v in res.values())/len(res):.1f}s max {max(v['seconds'] for v in res.values()):.1f}s")
for f, (a, b) in tot.items(): print(f"  {f:12s} {a:2d}/{b:2d} {100*a/b:3.0f}%")
for w in wrong: print("  ", *w)
