"""Хөдөлгөөнгүй зураг → «амьд» 9:16 кадр (Cinematic reel хичээлийн AE аргыг ffmpeg-ээр).

  python photo_alive.py <зураг> <гаралт.mp4> [--dur 3] [--push 1.10] [--bw] [--look film|crt|glitch]

Давхарга (AE → ffmpeg): Exposure −0.5 → eq; Deep Glow (radius 125, screen) → gblur + blend=screen;
Noise 12% → noise; Transform shake (expression) → crop-ийн sin() шилжилт; Camera push → zoompan;
Lens blur (гүн) → ирмэгээр нь blur хийсэн маск (vignette + gblur); Film dust → flicker + vignette.
look: film (анхдагч) · crt (scanline, RGB зөрөө, муруй) · glitch (RGB салалт, хэвтээ таслалт).
"""
import argparse, subprocess, sys

W, H, FPS = 720, 1280, 30


def graph(dur, push, bw, look):
    n = int(dur * FPS)
    z = f"zoompan=z='1+({push}-1)*on/{n}':x='iw/2-(iw/zoom/2)+sin(on/9)*3':y='ih/2-(ih/zoom/2)+cos(on/11)*3':d={n}:s={W*2}x{H*2}:fps={FPS}"
    base = (f"[0]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
            + ("hue=s=0," if bw else "") + f"eq=brightness=-0.04:contrast=1.12:gamma=0.95,{z},scale={W}:{H},format=gbrp,split=3[a][g][d];")
    # format=gbrp: blend-ийг RGB-д хийнэ — YUV-д өнгө ягаан болдог
    glow = "[g]gblur=sigma=28,eq=brightness=-0.15[gl];[a][gl]blend=all_mode=screen:all_opacity=0.35[x];"
    dof = "[d]gblur=sigma=6[bl];[x][bl]blend=all_expr='A*(1-min(1,hypot(X-W/2,Y-H*0.45)/(W*0.75)))+B*min(1,hypot(X-W/2,Y-H*0.45)/(W*0.75))'[y];"
    tail = "[y]noise=alls=12:allf=t+u,vignette=angle=PI/4.5,eq=brightness='0.02*sin(t*23)':eval=frame"
    if look == "crt":
        tail += (",rgbashift=rh=2:bh=-2,geq=lum='lum(X,Y)*(0.82+0.18*mod(Y,3))':cb='cb(X,Y)':cr='cr(X,Y)',"
                 "lenscorrection=k1=0.06:k2=0.02")
    elif look == "glitch":
        tail += (",rgbashift=rh=6:bh=-6:enable='gt(mod(n,17),14)',"
                 "hue=h=12:s=1.6:enable='eq(mod(n,23),0)',negate=enable='eq(mod(n,41),0)'")
    return base + glow + dof + tail + f",format=yuv420p[out]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--dur", type=float, default=3)
    ap.add_argument("--push", type=float, default=1.10); ap.add_argument("--bw", action="store_true")
    ap.add_argument("--look", choices=["film", "crt", "glitch"], default="film")
    a = ap.parse_args()
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-loop", "1", "-i", a.src, "-filter_complex", graph(a.dur, a.push, a.bw, a.look),
           "-map", "[out]", "-t", str(a.dur), "-r", str(FPS), "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", a.out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-1500:])
    print("✓", a.out)


if __name__ == "__main__":
    main()
