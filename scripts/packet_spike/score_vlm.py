import json, re, sys
sys.path.insert(0, "/private/tmp/claude-501/-Users-matt-PycharmProjects-AllotmentPlanner/45df2c81-97f5-499e-b2f6-db0e0caaf28d/scratchpad/scripts")
from labels import LABELS
path = sys.argv[1]
res = json.load(open(path))
def parse(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None
norm = lambda s: re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("'", "")).strip()
def has(hay, needle): return all(w in norm(hay).split() or w in norm(hay) for w in norm(needle).split())
score = {k: [0, 0] for k in ("name", "variety", "supplier", "seeds", "depth", "germinate", "best_before")}
bad = []
def put(field, ok, key, got, want):
    score[field][1] += 1; score[field][0] += bool(ok)
    if not ok: bad.append((key, field, got, want))
unparsed = 0
for k, lab in LABELS.items():
    r = res.get("029_" + k) or res.get("PXL_20261029_" + k) or next((v for kk, v in res.items() if kk.endswith(k)), None)
    if r is None: continue
    d = parse(r["raw"])
    if d is None: unparsed += 1; d = {}
    mname, mvar = d.get("name"), d.get("variety")
    if lab["name"] != "?": put("name", mname and has(mname, lab["name"]), k, mname, lab["name"])
    if lab["variety"]:
        put("variety", has((mvar or "") + " " + (mname or ""), lab["variety"]), k, (mvar, mname), lab["variety"])
    else:
        put("variety", not mvar or norm(mvar) in ("mixed", "mix"), k, mvar, None)
    put("supplier", d.get("supplier") and norm(lab["supplier"]).split()[-1][:7] in norm(d["supplier"]), k, d.get("supplier"), lab["supplier"])
    n = d.get("seeds_in_packet")
    put("seeds", (n == lab["seeds"]) if lab["seeds"] else n in (None, 0), k, n, lab["seeds"])
    dp = d.get("sow_depth_mm")
    put("depth", (dp is not None and abs(float(dp) - lab["depth"]) < 1) if lab["depth"] else dp is None, k, dp, lab["depth"])
    g = (d.get("germinate_days_min"), d.get("germinate_days_max"))
    want = lab["g"] or (None, None)
    put("germinate", tuple(g) == tuple(want) or (lab["g"] and None not in g and tuple(map(float, g)) == tuple(map(float, want))), k, g, want)
    by = d.get("best_before_year")
    put("best_before", (str(by) == str(lab["bb"])) if lab["bb"] else by in (None, "null"), k, by, lab["bb"])
print(f"{len(res)} packets, {unparsed} unparseable, mean {sum(v['seconds'] for v in res.values())/len(res):.1f} s, max {max(v['seconds'] for v in res.values()):.1f} s")
for f, (a, b) in score.items(): print(f"  {f:12s} {a:2d}/{b:2d}  {100*a/b:3.0f}%")
print("\nmisses:")
for k, f, got, want in bad: print(f"  {k} {f}: got {got!r}  want {want!r}")
