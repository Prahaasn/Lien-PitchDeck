import json, sys
from faster_whisper import WhisperModel

MODEL = sys.argv[1] if len(sys.argv) > 1 else "small"
takes = ["01-om-part1", "02-kanav", "03-prahaas", "04-all3-om-end"]

model = WhisperModel(MODEL, device="cpu", compute_type="int8")
for t in takes:
    segs, info = model.transcribe(
        f"{t}.wav", word_timestamps=True, language="es",
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=250),
    )
    words, seglist = [], []
    for s in segs:
        seglist.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        for w in (s.words or []):
            words.append({"start": round(w.start, 2), "end": round(w.end, 2), "w": w.word.strip()})
    json.dump({"take": t, "words": words, "segments": seglist},
              open(f"{t}.words.json", "w"), ensure_ascii=False, indent=0)
    print(f"\n=== {t}  ({len(words)} words, {len(seglist)} segments) ===")
    for s in seglist:
        print(f"  [{s['start']:6.2f} - {s['end']:6.2f}] {s['text']}")
