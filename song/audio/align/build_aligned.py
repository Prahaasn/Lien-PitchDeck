#!/usr/bin/env python3
"""Beat-lock each sung line to its target cue and remix over the instrumental.

For every line we know (a) where it is sung in the raw take (first-word onset,
from Whisper word timestamps) and (b) where it must land in the song (target
cue from the timing script). We take only the voiced span of each line, place
it at its target beat, and compress it *only* if the voice overruns its slot.
Never stretch -> no watery slowdowns; gaps between fast-sung lines are just
filled by the instrumental.
"""
import json, os, subprocess, math

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
ASR  = os.path.join(HERE, "..", "asr")
OUT  = os.path.join(HERE, "..", "output")
STEM = os.path.join(HERE, "stems")
os.makedirs(STEM, exist_ok=True); os.makedirs(OUT, exist_ok=True)

SONG_LEN = 205.0
MAX_TEMPO = 2.0          # never speed a line more than 2x
INST_VOL  = 0.5

# (onset_in_recording, target_in_song) per line; runs split for dropped audio.
TAKES = {
  "om": {"src": "01-om-part1.m4a", "runs": [
      {"end_rec": 67.5, "end_tgt": 78, "lines": [
        (7.5,8),(10.0,11),(12.2,14),(15.9,17),(17.9,20),(21.1,23),(22.9,26),
        (25.6,29),(27.7,30),(31.0,34),(33.5,38),(36.0,42),(40.1,46),(42.9,50),
        (45.4,52),(48.1,53.5),(50.8,55.5),(53.1,58),(55.0,62),(57.9,66),(66.1,76)]}]},
  "kanav": {"src": "02-kanav.m4a", "runs": [
      {"end_rec": 55.5, "end_tgt": 151, "lines": [
        (5.7,78),(7.0,81),(8.1,84),(10.0,87),(12.0,90),(14.0,93),(15.0,96),
        (18.0,99),(20.0,102),(22.8,106),(25.1,110),(28.0,114),(30.0,118),
        (32.4,120),(34.9,122),(37.1,124),(39.8,126),(41.5,130),(43.4,134),
        (44.9,138),(47.6,142),(50.3,145),(51.7,147),(53.1,149)]}]},
  "prahaas": {"src": "03-prahaas.m4a", "runs": [
      {"end_rec": 44.0, "end_tgt": 174, "lines": [
        (6.0,150),(10.7,152),(15.7,154),(19.9,156),(22.1,158),(27.7,160),
        (30.0,162),(32.6,164),(35.0,166),(37.7,168),(40.1,170),(42.6,172)]},
      {"end_rec": 62.3, "end_tgt": 189, "lines": [
        (50.8,174),(55.1,178),(57.9,182),(60.2,186)]}]},
  "all3": {"src": "04-all3-om-end.m4a", "runs": [
      {"end_rec": 16.5, "end_tgt": 204, "lines": [
        (0.11,190),(3.25,192),(5.41,194),(7.61,196),(9.67,198),
        (11.11,200),(12.21,201),(14.43,202)]}]},
}

def words_for(take):
    j = json.load(open(os.path.join(ASR, f"{take['src'].rsplit('.',1)[0]}.words.json")))
    return j["words"]

def voice_end(words, start, next_start):
    """Latest word-end strictly before the next line's onset."""
    ends = [w["end"] for w in words if start - 0.05 <= w["start"] < next_start - 0.05]
    return max(ends) if ends else next_start

def build_stem(name, take):
    words = words_for(take)
    chunks = []  # (rec_start, rec_end, tgt, out_dur)
    for run in take["runs"]:
        L = run["lines"]
        for i,(rec,tgt) in enumerate(L):
            nxt_rec = L[i+1][0] if i+1 < len(L) else run["end_rec"]
            nxt_tgt = L[i+1][1] if i+1 < len(L) else run["end_tgt"]
            vend = voice_end(words, rec, nxt_rec)
            vdur = max(0.15, vend - rec)
            slot = nxt_tgt - tgt
            tempo = min(MAX_TEMPO, max(1.0, vdur/slot))
            out_dur = vdur / tempo
            chunks.append((rec, vend, tgt, tempo, out_dur))
    # build filtergraph: one input, split into N, trim/tempo/fade/delay each, amix
    n = len(chunks)
    src = os.path.join(RAW, take["src"])
    parts = [f"[0:a]aformat=channel_layouts=stereo:sample_rates=48000,"
             f"highpass=f=85,loudnorm=I=-14:TP=-1.0:LRA=11,asplit={n}" +
             "".join(f"[s{i}]" for i in range(n))]
    mixin = []
    for i,(rs,re_,tgt,tempo,od) in enumerate(chunks):
        f = f"[s{i}]atrim=start={rs:.3f}:end={re_:.3f},asetpts=PTS-STARTPTS"
        if tempo > 1.001: f += f",atempo={tempo:.4f}"
        fo = max(0.0, od-0.03)
        f += f",afade=t=in:st=0:d=0.01,afade=t=out:st={fo:.3f}:d=0.03"
        f += f",adelay={int(tgt*1000)}|{int(tgt*1000)}[c{i}]"
        parts.append(f); mixin.append(f"[c{i}]")
    parts.append("".join(mixin) + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
                 f"apad=whole_dur={SONG_LEN}[out]")
    fg = ";".join(parts)
    dst = os.path.join(STEM, f"{name}.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",src,
                    "-filter_complex",fg,"-map","[out]",dst], check=True)
    print(f"  {name}: {n} lines  (tempo range "
          f"{min(c[3] for c in chunks):.2f}-{max(c[3] for c in chunks):.2f})")
    return dst

print("Building beat-locked stems:")
stems = {name: build_stem(name, t) for name,t in TAKES.items()}

# Final mix: instrumental + 4 positioned stems
inst = os.path.join(RAW, "instrumental.mp3")
ins  = ["-i", inst] + sum([["-i", s] for s in stems.values()], [])
fg = (f"[0:a]aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
      + "".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
      + "[bg]" + "".join(f"[v{i}]" for i in range(len(stems)))
      + f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,afade=t=out:st=202:d=3[out]")
dst = os.path.join(OUT, "subjuntivo-draft2.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y", *ins,
                "-filter_complex",fg,"-map","[out]","-c:a","libmp3lame","-q:a","2",dst], check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","csv=p=0",dst], capture_output=True, text=True).stdout.strip(), "sec")
