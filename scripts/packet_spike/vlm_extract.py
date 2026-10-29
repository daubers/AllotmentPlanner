import sys, os, json, time, glob, re
import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

device = sys.argv[1]            # mps | cpu
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 999
out_path = sys.argv[3] if len(sys.argv) > 3 else f"/private/tmp/claude-501/-Users-matt-PycharmProjects-AllotmentPlanner/45df2c81-97f5-499e-b2f6-db0e0caaf28d/scratchpad/out/vlm_{device}.json"
MAXPX = int(os.environ.get("MAXPX", str(1024 * 28 * 28)))
torch.set_num_threads(int(os.environ.get("THREADS", "8")))
model_id = "Qwen/Qwen2-VL-2B-Instruct"
t0 = time.time()
dtype = torch.bfloat16 if device == "cpu" else torch.float16
model = Qwen2VLForConditionalGeneration.from_pretrained(model_id, dtype=dtype).to(device).eval()
proc = AutoProcessor.from_pretrained(model_id, min_pixels=256 * 28 * 28, max_pixels=MAXPX)
print("loaded in", round(time.time() - t0, 1), "s", flush=True)

PROMPT = """This is a photo of a seed packet. Read it and reply with ONLY a JSON object with these keys. Use null for anything you cannot see on the packet. Do not guess.
{"name": plant name e.g. "Carrot",
 "variety": variety name e.g. "Nantes 2" or null,
 "supplier": the seed company,
 "latin_name": botanical name or null,
 "seeds_in_packet": number or null,
 "sow_depth_mm": sowing depth in millimetres (convert cm) or null,
 "spacing_plant_cm": number or null,
 "spacing_row_cm": number or null,
 "germinate_days_min": number or null,
 "germinate_days_max": number or null,
 "best_before_year": the year after "sow by" / "best before" as a 4-digit number, or null,
 "months_in_words": {"sow_indoors": text or null, "sow_outdoors": text or null, "harvest": text or null} (only if the packet writes months as words, e.g. "March to June"),
 "text_upright": true if the packet text reads horizontally the right way up in the photo, else false}"""

files = sorted(glob.glob("/private/tmp/claude-501/-Users-matt-PycharmProjects-AllotmentPlanner/45df2c81-97f5-499e-b2f6-db0e0caaf28d/scratchpad/packets/*.jpg"))[:limit]
results = {}
if os.path.exists(out_path): results = json.load(open(out_path))
for f in files:
    key = os.path.basename(f)[9:21]
    if key in results: continue
    img = Image.open(f).convert("RGB")
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    text = proc.apply_chat_template(msgs, add_generation_prompt=True)
    inputs = proc(text=[text], images=[img], return_tensors="pt").to(device)
    n_in = inputs["input_ids"].shape[1]
    t = time.time()
    with torch.no_grad():
        gen = model.generate(**inputs, max_new_tokens=360, do_sample=False)
    dt = time.time() - t
    raw = proc.batch_decode(gen[:, n_in:], skip_special_tokens=True)[0]
    results[key] = {"raw": raw, "seconds": round(dt, 1), "input_tokens": n_in}
    print(key, round(dt, 1), "s", n_in, "tok", raw.replace("\n", " ")[:230], flush=True)
    json.dump(results, open(out_path, "w"), indent=1)
