"""Gera assets/pdf2md.ico (documento com dobra + seta + 'MD')."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# folha com canto dobrado
fold = 60
sheet = [(40, 12), (216 - fold, 12), (216, 12 + fold), (216, 244), (40, 244)]
d.polygon(sheet, fill=(255, 255, 255), outline=(60, 60, 60), width=6)
d.polygon([(216 - fold, 12), (216 - fold, 12 + fold), (216, 12 + fold)], fill=(210, 210, 210), outline=(60, 60, 60), width=6)

# faixa vermelha "PDF"
d.rounded_rectangle((20, 70, 170, 122), radius=10, fill=(200, 30, 40))
# faixa azul "MD"
d.rounded_rectangle((86, 168, 236, 220), radius=10, fill=(30, 90, 200))


def font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


f = font(42)
d.text((95, 96), "PDF", font=f, fill="white", anchor="mm")
d.text((161, 194), "MD", font=f, fill="white", anchor="mm")
# seta
d.line((70, 132, 70, 180, 80, 180), fill=(60, 60, 60), width=8)
d.polygon([(78, 166), (78, 194), (96, 180)], fill=(60, 60, 60))

out = Path(__file__).resolve().parent.parent / "assets" / "pdf2md.ico"
out.parent.mkdir(exist_ok=True)
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(out.with_suffix(".png"))
print(out)
