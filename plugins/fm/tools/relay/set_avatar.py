# Set this device's Discord bot avatar (🖥️ PC = blue monitor, 🍎 Mac = black apple-ish). Run once per device.
import base64, io, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fmconfig  # noqa: E402  (DEVICE: env FMOS_DEVICE > ~/.fmos/config.json "device" > platform)
import requests
from PIL import Image, ImageDraw

mac = (fmconfig.DEVICE == "Mac") if fmconfig.DEVICE in ("Mac", "PC") else fmconfig.IS_MAC
S = 512
im = Image.new("RGB", (S, S), (20, 20, 20) if mac else (27, 92, 255))
d = ImageDraw.Draw(im)
if mac:
    # MacBook (BD 2026-10-03: алим хэтэрхий энгийн → Mac компьютерийн icon)
    d.rounded_rectangle([116, 130, 396, 320], 18, fill=(205, 208, 214))   # lid
    d.rounded_rectangle([132, 146, 380, 304], 8, fill=(30, 34, 44))      # screen
    d.rectangle([148, 162, 364, 288], fill=(70, 110, 220))               # wallpaper
    d.ellipse([220, 190, 292, 262], fill=(150, 190, 255))
    d.rectangle([248, 136, 264, 142], fill=(30, 34, 44))                 # notch
    d.polygon([(76, 330), (436, 330), (412, 368), (100, 368)], fill=(205, 208, 214))  # base
    d.rounded_rectangle([216, 330, 296, 342], 4, fill=(160, 164, 172))   # trackpad lip
else:
    d.rounded_rectangle([96, 120, 416, 330], 28, fill="white")
    d.rounded_rectangle([120, 144, 392, 306], 14, fill=(27, 92, 255))
    d.rectangle([236, 330, 276, 386], fill="white")
    d.rounded_rectangle([170, 384, 342, 408], 12, fill="white")
buf = io.BytesIO(); im.save(buf, "PNG")
tok = (pathlib.Path.home() / ".fmos_discord_token").read_text().strip()
r = requests.patch("https://discord.com/api/v10/users/@me", headers={"Authorization": f"Bot {tok}"},
                   json={"avatar": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()})
print(r.status_code, r.json().get("username"))
