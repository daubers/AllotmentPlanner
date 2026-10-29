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

PROMPT = "Read the text on this seed packet and write it out in full, in plain text. Do not describe the image and do not give coordinates."

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
        gen = model.generate(**inputs, max_new_tokens=int(os.environ.get("NEWTOK","700")), do_sample=False)
    dt = time.time() - t
    raw = proc.batch_decode(gen[:, n_in:], skip_special_tokens=True)[0]
    results[key] = {"raw": raw, "seconds": round(dt, 1), "input_tokens": n_in}
    print(key, round(dt, 1), "s", n_in, "tok", raw.replace("\n", " ")[:230], flush=True)
    json.dump(results, open(out_path, "w"), indent=1)
