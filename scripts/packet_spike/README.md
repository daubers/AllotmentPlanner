# Packet-reading spike (AM-39)

Throwaway evaluation code, kept so AM-42 can start from it. **No photos are here**: they were the
user's real packets and were run from scratch space. The paths inside the scripts point there;
edit them to rerun. See `docs/seed-scanning-spike.md` for what it found.

- `calread.py`: reads a packet's colour-bar calendar from pixels (numpy, scipy, Pillow; no model).
- `labels.py`: the ground truth, written by hand from the photos.
- `score_cal.py`, `score_vlm.py`, `score_tr.py`: scoring against `labels.py`.
- `vlm_extract.py`, `vlm_transcribe.py`: Qwen2-VL-2B runs (structured JSON, and plain transcription).
