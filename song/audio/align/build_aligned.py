#!/usr/bin/env python3
"""Beat-lock with ONE constant speed per part (no tempo oscillation).

Each singer sang at a roughly steady pace that was slightly off the track's
tempo, so a single constant time-stretch per take lines the whole part up
while keeping the speed dead constant -- no speeding up / slowing down within
a part. T = (total recorded content) / (target span), anchored at the part's
first cue. Prahaas drops one off-topic ad-lib via a cut, but both halves run
at the SAME constant tempo so there's no audible speed change.
"""
import os, subprocess, math

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
OUT  = os.path.join(HERE, "..", "output")
SONG_LEN = 205.0
INST_VOL = 0.5

# spans = recorded [start,end] kept (multiple -> concatenated, dropping gaps);
# tgt0/tgt1 = where the part's first/last kept audio must land in the song.
TAKES = [
  {"name":"om",      "src":"01-om-part1.m4a",    "spans":[(7.5,67.5)],            "tgt0":8,   "tgt1":78},
  {"name":"kanav",   "src":"02-kanav.m4a",       "spans":[(5.7,55.5)],            "tgt0":78,  "tgt1":151},
  {"name":"prahaas", "src":"03-prahaas.m4a",     "spans":[(6.0,44.0),(50.8,62.3)],"tgt0":150, "tgt1":188},
  {"name":"all3",    "src":"04-all3-om-end.m4a", "spans":[(0.11,16.5)],           "tgt0":190, "tgt1":204},
]

def tempo_chain(f):
    if 0.5 <= f <= 2.0:
        return [f]
    n = math.ceil(abs(math.log(f) / math.log(2.0)))
    return [f ** (1.0 / n)] * n

def build(take):
    spans = take["spans"]
    content = sum(e - s for s, e in spans)
    target  = take["tgt1"] - take["tgt0"]
    T = content / target                       # one constant tempo
    chain = tempo_chain(T)
    n = len(spans)
    parts = [f"[0:a]aformat=channel_layouts=stereo:sample_rates=48000,asplit={n}" +
             "".join(f"[s{i}]" for i in range(n))]
    labels = []
    for i,(s,e) in enumerate(spans):
        parts.append(f"[s{i}]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[g{i}]")
        labels.append(f"[g{i}]")
    delay = int(take["tgt0"] * 1000)
    chain_f = "".join(f"atempo={t:.5f}," for t in chain)
    parts.append("".join(labels) +
                 f"concat=n={n}:v=0:a=1,{chain_f}"
                 f"highpass=f=85,loudnorm=I=-14:TP=-1.0:LRA=11,"
                 f"afade=t=in:st=0:d=0.03,"
                 f"adelay={delay}|{delay},apad=whole_dur={SONG_LEN}[out]")
    dst = os.path.join(HERE, "stems", f"{take['name']}.wav")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i", os.path.join(RAW, take["src"]),
                    "-filter_complex", ";".join(parts), "-map","[out]", dst], check=True)
    print(f"  {take['name']:9s} constant tempo {T:.3f}  ({content:.1f}s -> {target:.0f}s)")
    return dst

print("Building constant-speed parts:")
stems = [build(t) for t in TAKES]

inst = os.path.join(RAW, "instrumental.mp3")
ins  = ["-i", inst] + sum([["-i", s] for s in stems], [])
fg = (f"[0:a]aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
      + "".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
      + "[bg]" + "".join(f"[v{i}]" for i in range(len(stems)))
      + f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,afade=t=out:st=202:d=3[out]")
dst = os.path.join(OUT, "subjuntivo-draft4.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y", *ins,
                "-filter_complex", fg, "-map","[out]","-c:a","libmp3lame","-q:a","2",dst], check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                      "-of","csv=p=0",dst], capture_output=True, text=True).stdout.strip(), "sec")
