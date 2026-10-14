"""Gera as capturas de tela e o GIF do README a partir do PDF de exemplo (Lorem ipsum).

Uso: .venv\\Scripts\\python tools\\make_screenshots.py
(roda a janela fora da tela; as preferências usadas aqui não afetam as do usuário)
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")  # o modo offscreen não acha as fontes sozinho
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

TMP = Path(tempfile.mkdtemp(prefix="pdf2md_shots_"))
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(TMP))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

from pdf2md.app import MainWindow  # noqa: E402

IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
sample = TMP / "exemplo-lorem-ipsum.pdf"
shutil.copy(ROOT / "docs" / "exemplo" / "exemplo-lorem-ipsum.pdf", sample)

app = QApplication([])
app.setStyle("Fusion")
from PySide6.QtGui import QFont  # noqa: E402
app.setFont(QFont("Segoe UI", 9))
w = MainWindow()
w.resize(1200, 760)
w.show()
frames: list[tuple[Image.Image, int]] = []


def pump(secs=0.3):
    end = time.time() + secs
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def shot(name=None, ms=1500):
    pump()
    path = TMP / "frame.png"
    w.grab().save(str(path))
    img = Image.open(path).convert("RGB")
    if name:
        img.save(IMG / f"{name}.png", optimize=True)
    frames.append((img.copy(), ms))


def wait_worker():
    while w.thread:
        pump(0.1)


shot("01-inicio", 1500)
w.add_paths([str(sample)])
w.list.setCurrentRow(0)
shot(None, 1200)
w._select(w.engine, "docling")
w._select(w.ocr, "off")
shot("02-opcoes", 1800)
w.convert_selected()
pump(1.0)
shot("03-convertendo", 1500)
wait_worker()
w.tabs.setCurrentIndex(0)
shot("04-visualizado", 3000)
w.tabs.setCurrentIndex(1)
shot("05-markdown", 3000)
w.save_selected()
w.tabs.setCurrentIndex(0)
shot("06-salvo", 2500)

# GIF reduzido (largura 900 px) com paleta adaptativa
gif = []
for img, _ in frames:
    small = img.resize((900, int(img.height * 900 / img.width)), Image.LANCZOS)
    gif.append(small.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
gif[0].save(IMG / "demo.gif", save_all=True, append_images=gif[1:],
            duration=[ms for _, ms in frames], loop=0, optimize=True)
shutil.rmtree(TMP, ignore_errors=True)
print("ok:", sorted(p.name for p in IMG.iterdir()))
