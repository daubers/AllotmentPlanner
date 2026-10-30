import json, os, sys, urllib.request, secrets

BASE = "http://localhost:8000/api/v1"

def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        print(method, path, e.code, e.read()[:300], file=sys.stderr)
        raise

password = secrets.token_urlsafe(12)
email = f"screenshots-{secrets.token_hex(3)}@example.com"
reg = call("POST", "/auth/register", {"email": email, "display_name": "Sam Gardener", "password": password})
tok = reg["access_token"]
plot = call("POST", "/allotments", {"name": "Demo plot"}, tok)
pid = plot["id"]
F = f"/allotments/{pid}/features"

lat0, lon0 = 51.5008, -0.1246   # a patch of London lawn as the example site
dlat, dlon = 1 / 111320, 1 / (111320 * 0.6234)

def ring(x, y, w, h):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    return {"type": "Polygon", "coordinates": [[[lon0 + a * dlon, lat0 + b * dlat] for a, b in pts]]}

def feat(geometry, **props):
    return call("POST", F, {"type": "Feature", "geometry": geometry, "properties": props}, tok)

ids = {}
ids["boundary"] = feat(ring(-4, -4, 38, 24), name="Plot boundary", kind="boundary")["id"]
for i, (x, y) in enumerate([(0, 0), (8, 0), (16, 0)]):
    ids[f"bed{i+1}"] = feat(ring(x, y, 6, 2.4), name=f"Bed {i+1}", kind="bed")["id"]
ids["bed4"] = feat(ring(0, 6, 6, 2.4), name="Herb bed", kind="bed")["id"]
ids["path"] = feat(ring(-1, 3.2, 28, 1.2), name="Main path", kind="path")["id"]
ids["shed"] = feat(ring(24, 8, 3, 2.2), name="Shed", kind="shed")["id"]
ids["compost"] = feat(ring(22, 0, 2.2, 2.2), name="Compost", kind="compost")["id"]
ids["tree"] = feat({"type": "Point", "coordinates": [lon0 + 14 * dlon, lat0 + 9 * dlat]}, name="Apple tree", kind="tree", radius_m=2.2)["id"]
ids["butt"] = feat({"type": "Point", "coordinates": [lon0 + 29 * dlon, lat0 + 6 * dlat]}, name="Water butt", kind="water", radius_m=0.6)["id"]
call("PATCH", f"{F}/{ids['shed']}", {"properties": {"locked": True}}, tok)

T = f"/allotments/{pid}/tasks"
for title, feature in [("Sow carrots", "bed1"), ("Net the brassicas", "bed2"), ("Turn the compost", "compost"), ("Mend the shed door", "shed")]:
    call("POST", T, {"title": title, "feature_id": ids[feature]}, tok)

print(json.dumps({"email": email, "password": password, "allotment": pid, "token": tok, "features": ids}))
