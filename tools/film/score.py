"""Score for film.mp4: a slow pad that changes chord on each section, soft bells on the cuts (numpy only)."""
# Run from out/film after cut.py; durs mirrors the clip list in cut.py, so change both together.
import numpy as np, wave
SR, X = 48000, 0.45
durs = [3.0, 13.2, 6.0, 6.2, 7.2, 6.0, 3.2, 3.2, 3.2, 3.2, 3.2, 3.4]   # mirrors cut.py
starts, t = [], 0.0
for i, d in enumerate(durs):
    starts.append(t); t += d - (X if i < len(durs) - 1 else 0)
T = t; N = int(T * SR); tt = np.arange(N) / SR
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
# D major colour, one chord per section (MIDI notes)
chords = [[50, 57, 62, 66, 69], [50, 57, 64, 66, 69], [47, 54, 62, 66, 69], [43, 50, 59, 62, 66],
          [45, 52, 61, 64, 69], [50, 57, 62, 66, 71], [47, 54, 61, 66, 69], [43, 50, 57, 62, 66],
          [45, 52, 59, 64, 69], [47, 54, 62, 66, 71], [43, 50, 59, 62, 67], [50, 57, 62, 66, 69]]
pad = np.zeros(N)
for i, (s, ch) in enumerate(zip(starts, chords)):
    e = starts[i + 1] + X if i + 1 < len(starts) else T
    a, b = int(s * SR), int(min(e + 1.2, T) * SR)
    seg = tt[a:b] - s
    env = np.minimum(1, seg / 1.1) * np.clip((e + 1.2 - s - seg) / 1.2, 0, 1)
    for m in ch:
        f = hz(m); w = 0.0
        for k, g in ((1, 1), (2, .28), (3, .12), (4, .05)):
            for det in (-0.12, 0.12):
                w = w + g * np.sin(2 * np.pi * f * k * (1 + det / 1200 * 12) * seg + k * m)
        pad[a:b] += w * env * (0.55 if m < 52 else 0.28)
# slow breathing filter feel: amplitude swell
pad *= 0.85 + 0.15 * np.sin(2 * np.pi * tt / 6.0)
bells = np.zeros(N)
for i, s in enumerate(starts[1:], 1):
    for m, g in ((chords[i][-1] + 12, 1.0), (chords[i][-2] + 12, .5)):
        a = int(s * SR); seg = tt[a:a + 3 * SR] - s
        if len(seg) == 0: continue
        f = hz(m)
        v = (np.sin(2 * np.pi * f * seg) + .3 * np.sin(2 * np.pi * f * 2.76 * seg) * np.exp(-seg * 6)) * np.exp(-seg * 2.2)
        bells[a:a + len(v)] += g * v * np.minimum(1, seg / 0.004)
sub = np.zeros(N)
for i, (s, ch) in enumerate(zip(starts, chords)):
    e = starts[i + 1] + X if i + 1 < len(starts) else T
    a, b = int(s * SR), int(e * SR); seg = tt[a:b] - s
    sub[a:b] += np.sin(2 * np.pi * hz(ch[0] - 12) * seg) * np.minimum(1, seg / 0.8) * np.clip((e - s - seg) / 0.6, 0, 1)
dry = 0.30 * pad / np.abs(pad).max() + 0.10 * bells / np.abs(bells).max() + 0.22 * sub
# one-pole lowpass to soften the top end
y = np.empty_like(dry); acc = 0.0; k = 0.18
for i in range(N):
    acc += k * (dry[i] - acc); y[i] = acc
rng = np.random.default_rng(7)
ir_t = np.arange(int(2.8 * SR)) / SR
L = np.convolve if False else None
def verb(x, seed):
    r = np.random.default_rng(seed).standard_normal(len(ir_t)) * np.exp(-ir_t * 2.4)
    n = 1 << int(np.ceil(np.log2(len(x) + len(r))))
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(r, n), n)[:len(x)]
wl, wr = verb(y, 1), verb(y, 2)
wl, wr = wl / np.abs(wl).max(), wr / np.abs(wr).max()
ym = y / np.abs(y).max()
L_, R_ = 0.7 * ym + 0.45 * wl, 0.7 * ym + 0.45 * wr
fade = np.minimum(1, tt / 1.0) * np.clip((T - tt) / 2.5, 0, 1)
st = np.stack([L_ * fade, R_ * fade], 1); st /= np.abs(st).max() * 1.12
with wave.open("score.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype("<i2").tobytes())
print("score.wav", round(T, 2), "s; cuts at", [round(s, 2) for s in starts])
