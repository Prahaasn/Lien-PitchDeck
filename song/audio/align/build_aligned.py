#!/usr/bin/env python3
"""Natural voices: ONE gentle, uniform speed per part (no per-line spikes).

High-quality constant Rubber Band stretch per take -- never the per-line
time-map warp that made fast sections sound sped-up. Speed-ups are minimized
(Prahaas's section is given more room by starting the finale slightly later)
because speeding a voice up sounds worse than leaving it be. Vocals are loud
(-12 LUFS) and the instrumental is ducked.
"""
import os, subprocess

HERE = os.path.dirname(__file__)
RAW  = os.path.join(HERE, "..", "raw")
OUT  = os.path.join(HERE, "..", "output")
TMP  = os.path.join(HERE, "stems"); os.makedirs(TMP, exist_ok=True)
SR = 48000
SONG_LEN = 207.0
INST_VOL = 0.32
VOX_LUFS = -12

# tgt0/tgt1 = where the part's kept audio starts/ends in the song.
# OM kept gentle (loved as-is); Kanav unchanged (fine); Prahaas eased a lot by
# pushing the finale to 192 so his speed-up drops from ~1.30x to ~1.18x.
TAKES = [
  {"name":"om",      "src":"01-om-part1.m4a",    "spans":[(7.5,67.5)],             "tgt0":8,   "tgt1":78},
  {"name":"kanav",   "src":"02-kanav.m4a",       "spans":[(5.7,55.5)],             "tgt0":78,  "tgt1":151},
  {"name":"prahaas", "src":"03-prahaas.m4a",     "spans":[(6.0,44.0),(50.8,62.3)], "tgt0":150, "tgt1":192},
  {"name":"all3",    "src":"04-all3-om-end.m4a", "spans":[(0.11,16.5)],            "tgt0":192, "tgt1":206},
]

def build(take):
    name, spans = take["name"], take["spans"]
    n = len(spans)
    fc = ";".join(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]"
                  for i,(s,e) in enumerate(spans))
    fc += ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[o]"
    content = os.path.join(TMP, f"{name}.content.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-i",os.path.join(RAW,take["src"]),"-filter_complex",fc,
                    "-map","[o]","-ar",str(SR),"-ac","2",content],check=True)
    cdur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                "-of","csv=p=0",content],capture_output=True,text=True).stdout)
    span = take["tgt1"] - take["tgt0"]
    X = span / cdur                       # output/input duration (constant)
    warped = os.path.join(TMP, f"{name}.warped.wav")
    subprocess.run(["rubberband","-t",f"{X:.6f}","-c","6",content,warped],
                   check=True,capture_output=True)
    delay = int(take["tgt0"]*1000)
    stem = os.path.join(TMP, f"{name}.wav")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",warped,
        "-af",f"highpass=f=85,loudnorm=I={VOX_LUFS}:TP=-1.0:LRA=11,"
              f"afade=t=in:st=0:d=0.03,adelay={delay}|{delay},apad=whole_dur={SONG_LEN}",
        stem],check=True)
    pct = (X-1)*100
    tag = "natural" if abs(pct)<3 else (f"{abs(pct):.0f}% slower" if X>1 else f"{abs(pct):.0f}% faster")
    print(f"  {name:9s} {cdur:.1f}s -> {span:.0f}s   x{X:.3f}  ({tag})")
    return stem

print("Building natural constant-speed parts:")
stems = [build(t) for t in TAKES]

inst = os.path.join(RAW,"instrumental.mp3")
ins  = ["-i",inst]+sum([["-i",s] for s in stems],[])
fg = (f"[0:a]aformat=channel_layouts=stereo,volume={INST_VOL},apad=whole_dur={SONG_LEN}[bg];"
      +"".join(f"[{i+1}:a]aformat=channel_layouts=stereo[v{i}];" for i in range(len(stems)))
      +"[bg]"+"".join(f"[v{i}]" for i in range(len(stems)))
      +f"amix=inputs={len(stems)+1}:normalize=0:dropout_transition=0,"
       f"alimiter=limit=0.97,afade=t=out:st=204:d=3[out]")
dst = os.path.join(OUT,"subjuntivo-draft6.mp3")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*ins,
    "-filter_complex",fg,"-map","[out]","-c:a","libmp3lame","-q:a","2",dst],check=True)
print(f"\nBuilt {dst}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0",dst],capture_output=True,text=True).stdout.strip(),"sec")
