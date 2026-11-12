#!/usr/bin/env python3
"""meter.py - fm meter: командын PC нөөцийн хэрэглээг хэмжиж монголоор тайлбарлана (2026-11-12).

  python meter.py --label "inai build" [--note <vault note>] [--interval 1] -- <команд ...>

Командыг ажиллуулж гаралтыг нь шууд дамжуулна, exit code-ийг нь буцаана.
Секунд тутам: CPU %, RAM (систем, GB), GPU % ба VRAM (nvidia-smi), дискийн бичилт (MB, Windows typeperf),
нийт хугацаа. Төгсөхөд ~/.fmos/meter/YYYY-MM-DD-HHMM-<label>.json бичиж, тайлбар хэвлэнэ.
--note өгвөл тэр note-ийн «Өөрчлөлтийн түүх» хүснэгтэд (байхгүй бол төгсгөлд) `resources:` мөр нэмнэ (зөвхөн нэмнэ).

Ангилал (босго):
  🔴 хүнд : CPU дундаж >= 70% · GPU оргил >= 80% · VRAM оргил >= 80% · RAM оргил >= 85% · хугацаа >= 10 мин
  🟡 дунд : CPU дундаж >= 30% · CPU оргил >= 90% · GPU дундаж >= 30% · RAM оргил >= 70% · хугацаа >= 60 сек
  🟢 хөнгөн: бусад
Windows: CPU/RAM = ctypes (GetSystemTimes, GlobalMemoryStatusEx), диск = typeperf. Mac/Linux: CPU = /proc/stat
эсвэл loadavg (ойролцоо), RAM = /proc/meminfo (Mac-д алгасна). nvidia-smi алга бол GPU алгасна.
Процессын модны RAM хэмжихгүй (psutil-гүй) - зөвхөн системийн RAM. Pure Python 3.9+, stdlib only, daemon-гүй.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

IS_WIN = os.name == "nt"
METER_DIR = Path(os.path.expanduser("~")) / ".fmos" / "meter"
THRESH = {
    "heavy": {"cpu_avg": 70, "gpu_peak": 80, "vram_pct_peak": 80, "ram_pct_peak": 85, "wall_s": 600},
    "medium": {"cpu_avg": 30, "cpu_peak": 90, "gpu_avg": 30, "ram_pct_peak": 70, "wall_s": 60},
}
DISK_WARN_GB = 20
LEVEL_TXT = {"heavy": "🔴 хүнд", "medium": "🟡 дунд", "light": "🟢 хөнгөн"}


# ---------- системийн уншилт ----------
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def ram_gb():
    """(used_gb, total_gb) эсвэл None."""
    if IS_WIN:
        m = _MEMSTAT()
        m.dwLength = ctypes.sizeof(_MEMSTAT)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return (m.ullTotalPhys - m.ullAvailPhys) / 1e9, m.ullTotalPhys / 1e9
        return None
    try:
        info = dict(l.split(":", 1) for l in Path("/proc/meminfo").read_text().splitlines() if ":" in l)
        tot = int(info["MemTotal"].split()[0]) * 1024
        av = int(info["MemAvailable"].split()[0]) * 1024
        return (tot - av) / 1e9, tot / 1e9
    except Exception:
        return None


class CpuReader:
    """Дуудлага бүрт өмнөх дуудлагаас хойших системийн CPU %-ийг буцаана."""

    def __init__(self):
        self.approx = False
        self.prev = self._times()

    def _times(self):
        if IS_WIN:
            i, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
            f = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime
            return f(i), f(k) + f(u)  # kernel нь idle-ийг агуулна
        try:
            p = [int(x) for x in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:]]
            return p[3] + p[4], sum(p)
        except Exception:
            return None

    def read(self):
        cur = self._times()
        if cur is None or self.prev is None:
            if hasattr(os, "getloadavg"):
                self.approx = True
                return round(min(100.0, os.getloadavg()[0] / (os.cpu_count() or 1) * 100), 1)
            return None
        di, dt = cur[0] - self.prev[0], cur[1] - self.prev[1]
        self.prev = cur
        return round(max(0.0, min(100.0, (1 - di / dt) * 100)), 1) if dt > 0 else None


class StreamReader(threading.Thread):
    """Урт амьдардаг дэд процессын мөр бүрийг parse хийж хамгийн сүүлийн утгыг хадгална."""

    def __init__(self, cmd, parse):
        super().__init__(daemon=True)
        self.parse, self.last, self.proc = parse, None, None
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                         errors="replace",
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, ValueError):
            self.proc = None

    def run(self):
        if not self.proc:
            return
        for line in self.proc.stdout:
            v = self.parse(line)
            if v is not None:
                self.last = v

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def parse_nvsmi(line):
    """'37, 2048' -> (gpu%, vram_mb)."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)", line)
    return (float(m.group(1)), float(m.group(2))) if m else None


def parse_typeperf(line):
    """'"11/12/2026 10:00:01.123","123456.7"' -> bytes/sec; толгой мөр бол None."""
    parts = [p.strip().strip('"') for p in line.strip().split(",")]
    if len(parts) < 2 or not re.match(r"\d", parts[0]):
        return None
    try:
        return float(parts[1])
    except ValueError:
        return None


def gpu_total_mb():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return float(out.strip().splitlines()[0])
    except Exception:
        return None


# ---------- хэмжилт ----------
class Sampler(threading.Thread):
    def __init__(self, interval=1.0):
        super().__init__(daemon=True)
        self.interval, self.samples, self.notes = interval, [], []
        self._halt = threading.Event()
        self.cpu = CpuReader()
        self.vram_total_mb = gpu_total_mb()
        self.gpu = self.disk = None
        if self.vram_total_mb:
            self.gpu = StreamReader(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                                     "--format=csv,noheader,nounits", "-lms", str(int(interval * 1000))],
                                    parse_nvsmi)
        else:
            self.notes.append("GPU: nvidia-smi алга - GPU/VRAM хэмжээгүй")
        if IS_WIN and shutil.which("typeperf"):
            self.disk = StreamReader(["typeperf", r"\PhysicalDisk(_Total)\Disk Write Bytes/sec",
                                      "-si", str(max(1, int(interval)))], parse_typeperf)
        else:
            self.notes.append("Диск: бичилтийн хэмжүүр зөвхөн Windows (typeperf) дээр")
        if ram_gb() is None:
            self.notes.append("RAM: энэ үйлдлийн системд уншиж чадсангүй - алгасав")
        self.notes.append("RAM, диск = систем бүхэлдээ; процессын модны RAM хэмжээгүй (psutil-гүй)")

    def run(self):
        for r in (self.gpu, self.disk):
            if r:
                r.start()
        t0 = time.time()
        while not self._halt.wait(self.interval):
            s = {"t": round(time.time() - t0, 1), "cpu": self.cpu.read()}
            rg = ram_gb()
            if rg:
                s["ram_gb"], s["ram_total_gb"] = round(rg[0], 2), round(rg[1], 2)
            if self.gpu and self.gpu.last:
                s["gpu"], s["vram_gb"] = self.gpu.last[0], round(self.gpu.last[1] / 1024, 2)
            if self.disk and self.disk.last is not None:
                s["disk_wr_mbs"] = round(self.disk.last / 1e6, 2)
            self.samples.append(s)

    def stop(self):
        self._halt.set()
        self.join(timeout=5)
        for r in (self.gpu, self.disk):
            if r:
                r.stop()
        if self.cpu.approx:
            self.notes.append("CPU: loadavg-аар ойролцоо")


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"peak": round(max(vals), 1), "avg": round(sum(vals) / len(vals), 1)}


def summarize(samples, wall_s, interval=1.0, vram_total_gb=None):
    col = lambda k: [s.get(k) for s in samples]
    d = [v for v in col("disk_wr_mbs") if v is not None]
    return {
        "wall_s": round(wall_s, 1), "samples": len(samples),
        "cpu": _stats(col("cpu")), "ram_gb": _stats(col("ram_gb")),
        "ram_total_gb": next((s["ram_total_gb"] for s in samples if "ram_total_gb" in s), None),
        "gpu": _stats(col("gpu")), "vram_gb": _stats(col("vram_gb")), "vram_total_gb": vram_total_gb,
        "disk_write_mb": round(sum(d) * interval, 1) if d else None,
    }


def pct(part, whole):
    return part / whole * 100 if part is not None and whole else None


def classify(r):
    """('heavy'|'medium'|'light', [шалтгаан])."""
    cpu, gpu = r.get("cpu") or {}, r.get("gpu") or {}
    ram_p = pct((r.get("ram_gb") or {}).get("peak"), r.get("ram_total_gb"))
    vram_p = pct((r.get("vram_gb") or {}).get("peak"), r.get("vram_total_gb"))
    H, M = THRESH["heavy"], THRESH["medium"]
    checks = [
        ("heavy", cpu.get("avg"), H["cpu_avg"], "CPU дундаж {:.0f}%"),
        ("heavy", gpu.get("peak"), H["gpu_peak"], "GPU оргил {:.0f}%"),
        ("heavy", vram_p, H["vram_pct_peak"], "VRAM оргил {:.0f}%"),
        ("heavy", ram_p, H["ram_pct_peak"], "RAM оргил {:.0f}%"),
        ("heavy", r.get("wall_s"), H["wall_s"], "хугацаа {:.0f} сек"),
        ("medium", cpu.get("avg"), M["cpu_avg"], "CPU дундаж {:.0f}%"),
        ("medium", cpu.get("peak"), M["cpu_peak"], "CPU оргил {:.0f}%"),
        ("medium", gpu.get("avg"), M["gpu_avg"], "GPU дундаж {:.0f}%"),
        ("medium", ram_p, M["ram_pct_peak"], "RAM оргил {:.0f}%"),
        ("medium", r.get("wall_s"), M["wall_s"], "хугацаа {:.0f} сек"),
    ]
    for level in ("heavy", "medium"):
        why = [fmt.format(v) for lv, v, th, fmt in checks if lv == level and v is not None and v >= th]
        if why:
            return level, why
    return "light", []


def slug(label):
    s = re.sub(r"[^\w\-]+", "-", label.strip().lower()).strip("-")
    return s or "run"


def previous_run(label, meter_dir):
    best = None
    for p in Path(meter_dir).glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("label") == label and (best is None or d.get("started", "") > best.get("started", "")):
            best = d
    return best


def free_gb(path):
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return None


def fmt_dur(s):
    return f"{s:.1f} сек" if s < 60 else f"{int(s // 60)} мин {int(s % 60)} сек"


def explain(rec, prev=None):
    r, lines = rec["summary"], []
    level, why = rec["class"], rec["class_why"]
    lines.append(f"⏱ «{rec['label']}» — {LEVEL_TXT[level]}, {fmt_dur(r['wall_s'])}, exit {rec['exit_code']}"
                 + (f" ({', '.join(why)})" if why else ""))
    if r.get("cpu"):
        lines.append(f"  CPU: оргил {r['cpu']['peak']:.0f}%, дундаж {r['cpu']['avg']:.0f}%")
    if r.get("ram_gb"):
        tot = r.get("ram_total_gb")
        lines.append(f"  RAM: оргил {r['ram_gb']['peak']:.1f}" + (f" / {tot:.0f}" if tot else "")
                     + f" GB, дундаж {r['ram_gb']['avg']:.1f} GB")
    if r.get("gpu"):
        vt = r.get("vram_total_gb")
        vp = pct(r["vram_gb"]["peak"], vt) if r.get("vram_gb") else None
        lines.append(f"  GPU: оргил {r['gpu']['peak']:.0f}%, дундаж {r['gpu']['avg']:.0f}%"
                     + (f"; VRAM оргил {r['vram_gb']['peak']:.1f} / {vt:.0f} GB ({vp:.0f}%)" if vp is not None else ""))
    if r.get("disk_write_mb") is not None:
        lines.append(f"  Диск: ~{r['disk_write_mb']:.0f} MB бичив")
    if r["samples"] == 0:
        lines.append("  Хэт богино (< 1 сек) - нөөцийн дээж аваагүй, зөвхөн хугацаа.")
    if prev and prev.get("summary", {}).get("wall_s"):
        pw = prev["summary"]["wall_s"]
        ratio = r["wall_s"] / pw
        word = "удаан" if ratio > 1.15 else ("хурдан" if ratio < 0.87 else "ойролцоо")
        lines.append(f"  Өмнөх ({prev['started'][:16].replace('T', ' ')}): {fmt_dur(pw)}, "
                     f"{LEVEL_TXT.get(prev.get('class'), '?')} → одоо {ratio:.2f}× ({word})")
    else:
        lines.append("  Өмнөх хэмжүүр алга - энэ label-ийн анхны суурь.")
    adv = []
    if level == "heavy":
        adv.append("энэ ажлын үеэр өөр хүнд ажил (рендер, build, олон agent) бүү зэрэг ажиллуул - дараалалд оруул")
    elif level == "medium":
        adv.append("дунд ачаалал - хөнгөн ажилтай зэрэг болно, хоёр хүнд ажлыг бүү давхцуул")
    else:
        adv.append("хөнгөн - бусад ажилтай зэрэг ажиллуулж болно")
    vp = pct((r.get("vram_gb") or {}).get("peak"), r.get("vram_total_gb"))
    if vp is not None and vp >= 70:
        adv.append(f"VRAM {vp:.0f}% - 4K эсвэл зэрэг GPU ажилд хүрэлцэхгүй болж магадгүй")
    rp = pct((r.get("ram_gb") or {}).get("peak"), r.get("ram_total_gb"))
    if rp is not None and rp >= 85:
        adv.append(f"RAM {rp:.0f}% - Chrome, Premiere зэргийг хааж байж ажиллуул")
    fg = rec.get("free_gb")
    if fg is not None and fg < DISK_WARN_GB:
        adv.append(f"⚠ {rec['out_drive']} дээр зөвхөн {fg:.1f} GB сул зай үлдлээ (< {DISK_WARN_GB} GB) - цэвэрлэ")
    elif fg is not None:
        lines.append(f"  Сул зай ({rec['out_drive']}): {fg:.0f} GB")
    lines += [f"  → {a}" for a in adv]
    lines += [f"  ℹ {n}" for n in rec.get("notes", [])]
    return "\n".join(lines)


def resources_line(rec):
    r = rec["summary"]
    parts = [f"class={rec['class']}", f"wall={r['wall_s']}s"]
    for k in ("cpu", "gpu"):
        if r.get(k):
            parts.append(f"{k}_peak={r[k]['peak']}% {k}_avg={r[k]['avg']}%")
    if r.get("ram_gb"):
        parts.append(f"ram_peak={r['ram_gb']['peak']}GB")
    if r.get("vram_gb"):
        parts.append(f"vram_peak={r['vram_gb']['peak']}GB")
    if r.get("disk_write_mb") is not None:
        parts.append(f"disk_write={r['disk_write_mb']}MB")
    return f"resources: {rec['label']} · " + " ".join(parts) + f" · exit={rec['exit_code']}"


def append_to_note(note, rec):
    """«Өөрчлөлтийн түүх»/Changelog хүснэгтийн төгсгөлд мөр нэмнэ; хэсэг алга бол файлын төгсгөлд. Зөвхөн нэмнэ."""
    p = Path(note)
    lines = p.read_text(encoding="utf-8").split("\n")
    line = resources_line(rec)
    head = next((i for i, l in enumerate(lines) if re.match(r"#+\s*(Өөрчлөлтийн түүх|Changelog)", l, re.I)), None)
    if head is None:
        while lines and lines[-1] == "":
            lines.pop()
        lines += ["", "- " + line, ""]
    else:
        j = head + 1
        while j < len(lines) and not lines[j].startswith("#") and not lines[j].lstrip().startswith("|"):
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith("|"):
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            lines.insert(j, f"| {rec['started'][:10]} | fm meter | `{line}` |")
        else:
            lines.insert(head + 1, "- " + line)
    p.write_text("\n".join(lines), encoding="utf-8")


def run(label, cmd, note=None, interval=1.0, meter_dir=METER_DIR, cwd=None):
    meter_dir = Path(meter_dir)
    meter_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    sampler = Sampler(interval)
    sampler.start()
    t0 = time.time()
    try:
        # Windows-д npm гэх мэт .cmd-ийг олохын тулд shell (жагсаалтыг list2cmdline-аар)
        proc = subprocess.Popen(subprocess.list2cmdline(cmd) if IS_WIN else cmd, shell=IS_WIN, cwd=cwd)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            code = proc.wait()
    except FileNotFoundError:
        print(f"meter: команд олдсонгүй: {cmd[0]}", file=sys.stderr)
        code = 127
    wall = time.time() - t0
    sampler.stop()
    vt = round(sampler.vram_total_mb / 1024, 2) if sampler.vram_total_mb else None
    summ = summarize(sampler.samples, wall, interval, vt)
    level, why = classify(summ)
    wd = str(Path(cwd or os.getcwd()).resolve())
    out_drive = Path(wd).anchor or "/"
    fg = free_gb(out_drive)
    rec = {"label": label, "cmd": cmd, "cwd": wd, "started": started.isoformat(timespec="seconds"),
           "exit_code": code, "summary": summ, "class": level, "class_why": why, "thresholds": THRESH,
           "out_drive": out_drive, "free_gb": round(fg, 1) if fg is not None else None,
           "notes": sampler.notes, "samples": sampler.samples}
    prev = previous_run(label, meter_dir)
    path = meter_dir / f"{started:%Y-%m-%d-%H%M}-{slug(label)}.json"
    n = 2
    while path.exists():
        path = meter_dir / f"{started:%Y-%m-%d-%H%M}-{slug(label)}-{n}.json"
        n += 1
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    text = explain(rec, prev)
    print("\n" + text + f"\n  JSON: {path}", flush=True)
    if note:
        try:
            append_to_note(note, rec)
            print(f"  Note-д нэмэв: {note}")
        except OSError as e:
            print(f"  Note-д бичиж чадсангүй: {e}", file=sys.stderr)
    return code, rec, text


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("Хэрэглээ: meter.py --label X [--note path] [--interval 1] -- <команд ...>", file=sys.stderr)
        return 2
    i = argv.index("--")
    ap = argparse.ArgumentParser(prog="meter.py")
    ap.add_argument("--label", required=True)
    ap.add_argument("--note")
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args(argv[:i])
    cmd = argv[i + 1:]
    if not cmd:
        print("meter: команд өгөөгүй", file=sys.stderr)
        return 2
    return run(a.label, cmd, a.note, a.interval)[0]


if __name__ == "__main__":
    sys.exit(main())
