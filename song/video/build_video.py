#!/usr/bin/env python3
"""Animated karaoke lyric video synced to the final mix.

Each line's on-screen time is computed from the SAME constant stretch used to
build the audio, so the highlight tracks the actual vocals. Words sweep-fill
(\\kf) in time; a section label and title intro sit on an audio-reactive
waveform background.
"""
import os, subprocess

HERE = os.path.dirname(__file__)
AUDIO = os.path.join(HERE, "..", "audio", "output", "subjuntivo-draft7.mp3")
ASS = os.path.join(HERE, "lyrics.ass")
OUT = os.path.join(HERE, "subjuntivo-video-final.mp4")
W, H = 1280, 720

# Each part: span mapping (rec0,rec_end)->(tgt0,tgt1) and lines (rec_onset,text).
# Multi-span (Prahaas) concatenates, dropping the ad-lib gap.
PARTS = [
 {"label":"OM","spans":[(7.5,67.5)],"tgt0":8,"tgt1":78,"lines":[
   (7.5,"Yeah, it's subjuntivo"),(10.0,"Used for doubt and emotion"),
   (12.2,"Cuando something's uncertain"),(15.9,"Or there's no confirmation"),
   (17.9,"Quiero que estudies"),(21.1,"Espero que vengas"),
   (22.9,"Dudo que comprenda"),(25.6,"Y ojalá aprendas"),
   (27.7,"No creo que sea fácil"),(31.0,"Pero vamos a intentar"),
   (33.5,"Es posible que aprendan"),(36.0,"Si empiezan a practicar"),
   (40.1,"Es importante que practiques"),(42.9,"Antes del examen"),
   (45.4,"Me alegra que estés aquí"),(48.1,"Y que todos lo capten"),
   (50.8,"Cuando hay recomendaciones"),(53.1,"Or feelings that you show"),
   (55.0,"That's when subjuntivo"),(57.9,"Is the verb mood that you know"),
   (60.8,"Whoa-oh-oh"),(62.8,"Whoa-oh-oh"),(64.4,"Yeah, yeah, yeah"),
   (66.1,"Subjuntivo please")]},
 {"label":"KANAV","spans":[(5.7,55.5)],"tgt0":78,"tgt1":151,"lines":[
   (5.7,'Start with the "yo" form'),(7.0,"Present indicative"),
   (8.1,'Drop the "o" right now'),(10.0,"Now make subjunctive"),
   (12.0,'AR changes into "e"'),(14.0,"Like hable y estudie"),
   (15.0,'ER and IR switch to "a"'),(18.0,"Coma and viva every day"),
   (20.0,"Hablo turns to hable"),(22.8,"Comer changes coma"),
   (25.1,"Vivir changes viva"),(28.0,"Ahora ya funciona"),
   (30.0,"No facts or certainty"),(32.4,"That's the biggest clue"),
   (34.9,"If there's hope or emotion"),(37.1,"Subjuntivo comes through"),
   (39.8,"Antes de que llegues"),(41.5,"Para que pueda estudiar"),
   (43.4,"Usamos subjuntivo"),(44.9,"Cuando no hay realidad"),
   (47.6,"Whoa-oh-oh"),(50.3,"Whoa-oh-oh"),
   (51.7,"Now we know the way"),(53.1,"Subjuntivo every day")]},
 {"label":"PRAHAAS","spans":[(6.0,44.0),(50.8,62.3)],"tgt0":150,"tgt1":200,"lines":[
   (6.0,"Now the irregulars"),(10.7,"Yeah DISHES is the key"),
   (15.7,"Dar becomes dé"),(19.9,"And ser changes sea"),
   (22.1,"Ir becomes vaya"),(27.7,"Haber changes haya"),
   (30.0,"Estar turns esté"),(32.6,"Saber changes sepa"),
   (35.0,"These verbs are irregular"),(37.7,"But easy if you practice"),
   (40.1,"Learn the conjugations"),(42.6,"And your Spanish will be fantastic"),
   (50.8,"No creo que sea difícil"),(55.1,"If you study every day"),
   (57.9,"Ojalá que recuerden"),(60.2,"Everything we say")]},
 {"label":"TODOS","spans":[(0.11,16.5)],"tgt0":200,"tgt1":217,"lines":[
   (0.11,"Emotion, doubt, and wishes"),(3.25,"Recommendations too"),
   (5.41,"That's exactly why"),(7.61,"We use subjuntivo"),
   (9.67,"Whoa-oh-oh"),(11.11,"Whoa-oh-oh"),
   (12.21,"Yeah, yeah, yeah"),(14.43,"Subjuntivo now")]},
]

def concat_time(spans, t):
    off = 0.0
    for s,e in spans:
        if s-1e-6 <= t <= e+1e-6: return off+(t-s)
        off += e-s
    return off

def tc(t):
    cs=int(round(t*100)); h=cs//360000; m=(cs//6000)%60; s=(cs//100)%60; c=cs%100
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"

# compute display start for every line
events=[]  # (start,end,label,text)
flat=[]
for p in PARTS:
    cdur=sum(e-s for s,e in p["spans"]); X=(p["tgt1"]-p["tgt0"])/cdur
    for rec,text in p["lines"]:
        st=p["tgt0"]+concat_time(p["spans"],rec)*X
        flat.append([st,text,p["label"],p["tgt1"]])
for i,(st,text,label,tgt1) in enumerate(flat):
    end=flat[i+1][0] if i+1<len(flat) else tgt1
    end=min(end, st+7.0)            # don't let a line linger too long
    events.append((st,max(st+0.6,end),label,text))

def karaoke(text,dur):
    words=text.split()
    weights=[len(w)+1 for w in words]; tot=sum(weights)
    out=""
    for w,wt in zip(words,weights):
        cs=max(8,int(round(dur*100*wt/tot)))
        out+=f"{{\\kf{cs}}}{w} "
    return out.strip()

HEAD=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,DejaVu Sans,52,&H0000F0FF,&H00FFFFFF,&H00301808,&H96000000,-1,0,0,0,100,100,0,0,1,3.5,2,5,80,80,0,1
Style: Label,DejaVu Sans,30,&H00F0C040,&H00F0C040,&H00301808,&H00000000,-1,0,0,0,100,100,2,0,1,2.5,0,8,0,0,40,1
Style: Title,DejaVu Sans,64,&H00FFFFFF,&H00FFFFFF,&H00401004,&H00000000,-1,0,0,0,100,100,0,0,1,4,3,5,0,0,0,1
Style: Sub,DejaVu Sans,32,&H00D0D0FF,&H00D0D0FF,&H00401004,&H00000000,0,0,0,0,100,100,0,0,1,2,2,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
lines=[HEAD]
# title intro
lines.append(f"Dialogue: 0,{tc(0.3)},{tc(7.8)},Title,,0,0,0,,{{\\pos({W//2},300)\\fad(400,500)}}El Subjuntivo")
lines.append(f"Dialogue: 0,{tc(0.3)},{tc(7.8)},Sub,,0,0,0,,{{\\pos({W//2},375)\\fad(400,500)}}\"Party in the U.S.A.\"   ·   Prahaas · Kanav · Om")
# section labels
for p in PARTS:
    st=p["tgt0"]; en=p["tgt1"]
    lines.append(f"Dialogue: 0,{tc(st)},{tc(en)},Label,,0,0,0,,{{\\pos({W//2},110)\\fad(250,250)}}{p['label']}")
# lyric lines
for st,en,label,text in events:
    lines.append(f"Dialogue: 1,{tc(st)},{tc(en)},Lyric,,0,0,0,,{{\\pos({W//2},380)\\fad(150,150)}}{karaoke(text,en-st)}")
open(ASS,"w").write("\n".join(lines)+"\n")
print(f"Wrote {ASS} ({len(events)} lyric lines)")

fc=(f"color=c=0x0A0E24:s={W}x{H}:d=207[base];"
    f"[0:a]showwaves=s={W}x170:mode=cline:colors=0x5A7CFF|0xB060FF:rate=25,"
    f"format=yuva420p,colorchannelmixer=aa=0.55[wav];"
    f"[base][wav]overlay=0:{H-180}[bg];"
    f"[bg]ass={ASS}[v]")
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",AUDIO,
    "-filter_complex",fc,"-map","[v]","-map","0:a","-t","222",
    "-c:v","libx264","-pix_fmt","yuv420p","-preset","medium","-crf","20",
    "-c:a","aac","-b:a","192k",OUT],check=True)

print(f"Built {OUT}")
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","csv=p=0",OUT],capture_output=True,text=True).stdout.strip(),"sec")
