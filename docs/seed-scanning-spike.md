# Seed packet reading: spike results (AM-39)

**Verdict: go, with a different design from the plan.** The calendar can be read from pixels very
reliably. A 2B vision-language model reads *who and what* a packet is well, but not the small-print
numbers, so numbers come from transcribing the text and parsing it in code. Every value goes to a
draft the user reviews; nothing is trusted blindly.

## What was tested

23 photos of the **backs of real packets**, as taken on a phone (sideways ones, torn ones, two
packets in one frame, a finger in shot): Mr Fothergill's (14), Suttons (7), Johnsons (3 with no
calendar graphic, months written in words). Ground truth was written by hand from the photos
(`scripts/packet_spike/labels.py`), with fields that are cut off or hidden recorded as "not visible".

Caveats: one small set; the calendar reader was tuned on these same 23 photos, so its real accuracy
on new packets will be lower; the calendar labels were checked by eye against crops of the reader's
own output, so they are not fully independent.

## 1. Calendar from pixels: works

No model. Segment the four palette colours (pink or coral, blue, green, yellow), find the bar, find
its 13 vertical grid lines from the dark valleys in the colour band, then read each month column.
Colours map by activity: pink sow indoors, blue sow outdoors, green plant out, yellow harvest (the
packets' legends agree across both brands).

| | |
|---|---|
| Packets with a graphic found | 20 of 20 |
| Calendars exactly right | 18 of 20 |
| Month-cells right | 957 of 960 (99.7%) |
| The 2 misses | a faint green "plant out" stripe in glare or blur (3 cells) |
| Time | about 2.4 s per rotation on a CPU, about 6 s trying all four |

Things it had to cope with, and does: a vertical calendar (Suttons' older pea packet), sideways and
curved packets, glare and shadow, stripes that split a month cell (sow above harvest), half-month
bars, an empty month in the middle, and legend swatches that look like cells.

Findings that shape the design:

- **Orientation can come from pixels.** Inside a month cell the stripes always run pink, green,
  blue, yellow from the top. Voting on that was never the wrong way round and decided 18 of 20; it
  can't decide when no cell has two colours (2 packets), so a month-label or text check is still
  needed as the tie-break.
- Valley positions alone were ambiguous by a column on 3 packets; anchoring on the strong outer
  frame lines and penalising lines that continue past either end fixed it.
- Johnsons packets have **no graphic**, only "March to June" in text. That needs the text path.
- The colour thresholds are brand-specific tuning, so a third supplier's palette will need checking.

## 2. Reading text with Qwen2-VL-2B

Run on the host's GPU (M2 Pro, fp16). Images went in as the phone took them.

| Field (scored on 23 packets) | JSON prompt, 1 MP | JSON prompt, 1.6 MP | Transcribe, then parse |
|---|---|---|---|
| Plant name | 100% | 100% | |
| Variety | 87% | 83% | |
| Supplier | 91% | 96% | |
| Seeds in packet | 65% | 78% | 35% |
| Sow depth | 35% | 35% | **65%** |
| Days to germinate | 30% | 30% | **78%** |
| "Sow by" year | 30% | 35% | 48% |
| Mean seconds per packet | 7.7 | 15.5 (worst 55) | 16.4 (worst 69) |

- Identity (name, variety, supplier) is good enough as a draft. Numbers are not: asking a small
  model for structured numbers fails mostly by saying "null", sometimes by being confidently wrong
  (depth 150 for 15, a 2023 date that was not there). Part of that is unit conversion the model
  should not be doing.
- **Transcribing and parsing in code is clearly better** (germination 30% to 78%, depth 35% to 65%)
  with regexes written once and not tuned, so that is a floor. The misses are mostly text that the
  transcription cut short (the "sow by" sticker at the bottom, the seed count in the corner badge),
  which a second pass over a crop of those regions should recover.
- Doubling the image size did not help the numbers and doubled the time. Not worth it.
- A first transcription attempt returned bounding-box coordinates instead of text; that was a prompt
  mistake and is not counted above.

## 3. Speed and where it can run

- Qwen2-VL-2B needs about 4.5 GB. The dev Docker VM has 5.8 GB, so it cannot run beside the stack
  there; it ran natively on the host.
- **It fits on the 8 GB AMD card (RX 6600) of the GPU worker (AM-55).** fp16 weights take 4.1 GB and
  the peak while reading a packet is 6.3 GB. Accuracy is identical to the Mac runs (same model, same
  prompts), so the only question was speed:

  | Where | JSON prompt | Transcribe |
  |---|---|---|
  | RX 6600, ROCm, fp16 | 14.8 s | 33.4 s |
  | That machine's CPU (12 cores, bf16) | 192 s | not run |
  | M2 Pro GPU, fp16 | 7.7 s | 16.4 s |

  The RX 6600 is about 13 times faster than that machine's CPU and about half the speed of the M2
  Pro. The first packet after the process starts takes about two minutes (the GPU kernels compile
  on first use, which ROCm does for chips it does not officially support); a long-running worker
  pays that once per restart. One packet with both passes is about 50 s on this card, so scanning
  a handful of packets at a time is fine and a whole drawer is a coffee-break job.
- Everything runs locally; nothing about a packet leaves the network.

## Recommended design for AM-42

1. **Calendar**: port `calread.py` into the mapper's `vision` queue, with the stripe-order and
   month-label orientation checks. Keep a colour-class table per supplier, and show the calendar
   crop beside the editable 12-month grid so a wrong read is obvious.
2. **Text**: one transcription pass (full image) plus a second pass over the bottom strip, parsed
   by `packet_text.py` (pure, table-tested): sow depth, germination days, seed count, "sow by" year
   (handling `DEC 2027`, `YE 2028`, `7/2024`), spacing, and calendar months written in words for
   packets with no graphic. A JSON-prompt pass supplies only name, variety and supplier.
3. **Review**: the draft shows every field editable, flags anything the parser could not find, and
   never becomes an active packet without the user pressing save. Duplicated packets in one frame
   (a torn packet showing another) need the user to crop or retake.
4. **Wrong-looking values** (a depth of 150 mm, a "sow by" in the past) are highlighted, not
   rejected.

## Not done / still open

- Persisting the GPU kernel cache across worker restarts (the 2-minute first call).
- A model larger than 2B: nothing bigger than about 3B fits in 8 GB at fp16, so a better reader of
  small print would need quantisation or a bigger card; not tried.
- A third supplier's palette; fronts of packets; barcodes (only the back was photographed).
- Tuning the parsers on fresh photos; this set was used for everything above.
- The photos used are in scratch space only, not in the repository. They should be deleted when
  the user says the spike is finished.
