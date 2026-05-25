#!/usr/bin/env python3
"""Beat-lock the takes WITHOUT chopping the lyrics.

Each take is split only at musical-phrase boundaries (~every 4 lines). Each
phrase is kept as one continuous chunk and gently time-warped (whole-phrase
tempo) so the phrase rides its target beat. Chunks within a run are
concatenated edge-to-edge -> no dropped words, no choppy per-line gaps. The
only hard cut is between Prahaas's two runs, which removes an off-topic ad-lib.
"""
import os, subprocess, math

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
OUT  = os.path.join(HERE, "..", "output")
SONG_LEN = 205.0
INST_VOL = 0.5

# Phrase anchors: (rec_onset, target). Each run also has an end (rec, target).
RUNS = [
  {"name":"om", "src":"01-om-part1.m4a", "start":8,
   "anchors":[(7.5,8),(17.9,20),(27.7,30),(40.1,46),(50.8,54),(60.5,70)],
   "end":(67.5,78)},
  {"name":"kanav", "src":"02-kanav.m4a", "start":78,
   "anchors":[(5.7,78),(12.0,90),(20.0,102),(30.0,118),(39.8,126),(47.6,142)],
   "end":(55.5,151)},
  {"name":"prahaas1", "src":"03-prahaas.m4a", "start":150,
   "anchors":[(6.0,150),(22.1,158),(35.0,166)],
   "end":(44.0,174)},
  {"name":"prahaas2", "src":"03-prahaas.m4a", "start":174,
   "anchors":[(50.8,174)],
   "end":(62.3,188)},
  {"name":"all3", "src":"04-all3-om-end.m4a", "start":190,
   "anchors":[(0.11,190),(9.67,198)],
   "end":(16.5,204)},
]

def tempo_chain(f):
    """Decompose tempo factor into stages each within [0.5, 2.0]."""
    if f >= 0.5 and f <= 2.0:
        return [f]
    n = math.ceil(abs(math.log(f) / math.log(2.0)))
    s = f ** (1.0 / n)
    return [s] * n

def build_run(run):
    pts = run["anchors"] + [run["end"]]
    segs = []
    for i in range(len(pts) - 1):
        rs, ts = pts[i]
        re_, te = pts[i+1]
        f = (re_ - rs) / (te - ts)          # >1 compress, <1 stretch
        segs.append((rs, re_, tempo_chain(f), f))
    n = len(segs)
    parts = [f"[0:a]aformat=channel_layouts=stereo:sample_rates=48000,asplit={n}" +
             "".join(f"[s{i}]" for i in range(n))]
    labels = []
    for i,(rs,re_,chain,f) in enumerate(segs):
        flt = f"[s{i}]atrim=start={rs:.3f}:end={re_:.3f},asetpts=PTS-STARTPTS"
        for t in chain:
            flt += f",atempo={t:.5f}"
        flt += f"[g{i}]"; parts.append(flt); labels.append(f"[g{i}]")
    delay = int(run["start"] * 1000)
    parts.append("".join(labels) +
                 f"concat=n={n}:v=0:a=1,"
                 f"highpass=f=85,loudnorm=I=-14:TP=-1.0:LRA=11,"
                 f"afade=t=in:st=0:d=0.03,"
                 f"adelay={delay}|{delay},apad=whole_dur={SONG_LEN}[out]")
    fg = ";".join(parts)
    dst = os.path.join(HERE, "stems", f"{run['name']}.wav")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i", os.path.join(RAW, run["src"]),
                    "-filter_complex", fg, "-map","[out]", dst], check=True)
    fr = ", ".join(f"{s[3]:.2f}" for s in segs)
    print(f"  {run['name']:9s} {n} phrases  tempo[{fr}]")
    return dst

print("Building continuous phrase-warped runs:")
stems = [build_run(r) for r in RUNS]

inst = os.path.join(RAW, "instrumental.mp3")
ins  = ["-i", inst] + sum([["-i", s] for s in stems], [])
fg = (f"[0:a]aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
      + "".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
      + "[bg]" + "".join(f"[v{i}]" for i in range(len(stems)))
      + f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,afade=t=out:st=202:d=3[out]")
dst = os.path.join(OUT, "subjuntivo-draft3.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y", *ins,
                "-filter_complex", fg, "-map","[out]","-c:a","libmp3lame","-q:a","2",dst], check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","csv=p=0",dst], capture_output=True, text=True).stdout.strip(), "sec")
