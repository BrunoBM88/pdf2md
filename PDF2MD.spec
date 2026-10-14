# PyInstaller: gera dist\PDF2MD\PDF2MD.exe (modo pasta; o Docling/PyTorch é grande demais para --onefile)
# Build:  .venv\Scripts\python -m PyInstaller PDF2MD.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas = [("assets", "assets")]
binaries = []
hiddenimports = ["pdf2md.shell_integration"]

for pkg in [
    "docling", "docling_core", "docling_parse", "docling_ibm_models",
    "rapidocr", "pymupdf4llm", "pymupdf", "markitdown", "magika",
]:
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# torchvision para Python 3.14 usa extensões ABI-estável (_C_stable.pyd, image_stable.pyd),
# que o hook padrão do PyInstaller não conhece
import glob, os, torchvision
for f in glob.glob(os.path.join(os.path.dirname(torchvision.__file__), "*_stable.pyd")):
    binaries.append((f, "torchvision"))

# transformers carrega submódulos de forma preguiçosa, varrendo os .py no disco
hiddenimports += collect_submodules("transformers")

for pkg in ["torch", "torchvision", "transformers", "huggingface_hub", "safetensors", "tokenizers"]:
    datas += copy_metadata(pkg)

a = Analysis(
    ["run.pyw"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "pytest"],
    noarchive=False,
    module_collection_mode={"transformers": "pyz+py", "docling_ibm_models": "pyz+py"},
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PDF2MD",
    icon="assets/pdf2md.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PDF2MD", upx=False)
