"""Cut the preview film from the live take and the Cycles stills (ffmpeg only)."""
# Run from out/film: it reads pc.mp4 (from tools/record.sh + frames.txt) and stills/ (tools/showcase.py).
import subprocess
W, H, FPS = 1600, 900, 30
G = "stills/showcase-"
F = "/usr/share/fonts/inter/InterVariable.ttf"
FR = F

def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")

def caption(text, dur, sub=None):
    a = f"if(lt(t,0.35),t/0.35,if(gt(t,{dur - 0.35}),({dur}-t)/0.35,1))"
    v = (f"drawtext=fontfile={F}:text='{esc(text)}':fontsize=30:fontcolor=white:x=88:y=h-292:alpha='{a}':"
         f"box=1:boxcolor=0x0b0f14@0.72:boxborderw=18")
    if sub:
        v += (f",drawtext=fontfile={FR}:text='{esc(sub)}':fontsize=21:fontcolor=0xc3ceda:x=88:y=h-236:alpha='{a}':box=1:boxcolor=0x0b0f14@0.72:boxborderw=12")
    return v

clips = []   # (input args, filter)
def take(t0, t1, text, sub):
    d = t1 - t0
    clips.append((["-ss", str(t0), "-t", str(d), "-i", "pc.mp4"], f"scale={W}:{H},{caption(text, d, sub)}", d))

def still(name, text, sub, d=3.2):
    zp = f"zoompan=z='1+0.045*on/{int(d * FPS)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(d * FPS)}:s={W}x{H}:fps={FPS}"
    clips.append((["-loop", "1", "-t", str(d), "-i", f"{G}{name}.png"],
                  f"scale=3200:1800,{zp},{caption(text, d, sub)}", d))

def card(title, sub, d):
    a = f"if(lt(t,0.5),t/0.5,if(gt(t,{d - 0.5}),({d}-t)/0.5,1))"
    clips.append((["-f", "lavfi", "-t", str(d), "-i", f"color=c=0x07090c:s={W}x{H}:r={FPS}"],
                  f"drawtext=fontfile={F}:text='{esc(title)}':fontsize=76:fontcolor=white:x=(w-tw)/2:y=h/2-70:alpha='{a}',"
                  f"drawtext=fontfile={FR}:text='{esc(sub)}':fontsize=28:fontcolor=0x7ad4f2:x=(w-tw)/2:y=h/2+30:alpha='{a}'", d))

card("Replicator", "You specify it, you build it.", 3.0)
take(0.4, 13.6, "Build", "104 operations play in order. Every step is a watertight solid from manifold3d.")
take(14.0, 20.0, "Dissect", "Each component slides out along its own axis, with callouts.")
take(20.0, 26.2, "Blueprint", "One control fades from technical drawing to full PBR.")
take(26.6, 33.8, "Showcase", "A product stage with soft shadows and a turntable.")
take(38.0, 44.0, "Drawing sheet", "Third-angle views, measured dimensions, a parts list with computed masses.")
still("gaming_pc_liquid", "Custom liquid loop", "47 parts, 18.2 kg. Path-traced in Cycles on the CPU.")
still("raspberry_pi_5", "Raspberry Pi 5", "85 x 56 mm board at real scale, 60 g with its standoffs.")
still("rocket_engine", "Gas-generator rocket engine", "Rao bell nozzle drawn from its throat radius and expansion ratio.")
still("house_two_bed", "Two-bedroom house", "Specified from one sentence: slab, walls, partitions, door and window openings, gable roof.")
still("house_sheet", "Its drawing sheet", "A floor plan cut at 1.2 m and two elevations, generated from the program.")
card("Replicator", "Houses, boards, machines, concepts. Built, checked and drawn.", 3.4)

args, chains, n = [], [], len(clips)
for i, (inp, flt, d) in enumerate(clips):
    args += inp
    chains.append(f"[{i}:v]{flt},fps={FPS},format=yuv420p,setsar=1[v{i}]")
X = 0.45
acc, off, prev = "v0", clips[0][2], "v0"
for i in range(1, n):
    out = f"x{i}"
    chains.append(f"[{prev}][v{i}]xfade=transition=fadeblack:duration={X}:offset={off - X:.3f}[{out}]")
    off += clips[i][2] - X
    prev = out
cmd = ["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(chains), "-map", f"[{prev}]",
       "-c:v", "libx264", "-crf", "20", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "film.mp4"]
subprocess.run(cmd, check=True)
print("film.mp4", round(off, 1), "s")
