"""Motores de conversão PDF -> Markdown."""
from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import pymupdf

# id do motor -> nome exibido
ENGINES = {
    "pymupdf4llm": "Rápido (PyMuPDF4LLM)",
    "docling": "Tabelas e layout + OCR (Docling)",
    "markitdown": "Simples (MarkItDown)",
}

# modos de OCR (só valem para o Docling)
OCR_MODES = {
    "auto": "Automático (só onde houver imagem)",
    "force": "Forçar em todas as páginas (PDF escaneado)",
    "off": "Desligado (mais rápido)",
}


@dataclass
class ConvertOptions:
    pages: str = ""              # ex.: "1-3,5" (vazio = todas)
    write_images: bool = False   # extrai imagens para uma pasta ao lado do .md
    output_dir: Path | None = None  # None = mesma pasta do PDF
    engine: str = "pymupdf4llm"
    ocr: str = "auto"


class ScannedPdfError(Exception):
    pass


def parse_pages(spec: str, page_count: int) -> list[int] | None:
    """Converte '1-3,5' em índices base 0. Vazio -> None (todas)."""
    spec = spec.strip()
    if not spec:
        return None
    result: set[int] = set()
    for part in spec.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a.strip() else 1
            end = int(b) if b.strip() else page_count
            result.update(range(start - 1, min(end, page_count)))
        else:
            n = int(part)
            if 1 <= n <= page_count:
                result.add(n - 1)
    if not result:
        raise ValueError(f"Intervalo de páginas inválido: '{spec}'")
    return sorted(result)


def output_path_for(pdf: Path, opts: ConvertOptions) -> Path:
    folder = opts.output_dir or pdf.parent
    return folder / (pdf.stem + ".md")


def image_dir_for(pdf: Path, opts: ConvertOptions) -> Path:
    md = output_path_for(pdf, opts)
    return md.parent / (md.stem + "_imagens")


def has_text_layer(pdf: Path, pages: list[int] | None = None) -> bool:
    with pymupdf.open(pdf) as doc:
        idx = pages if pages is not None else range(min(doc.page_count, 5))
        return any(doc[i].get_text().strip() for i in idx)


def convert(pdf: Path, opts: ConvertOptions) -> str:
    """Converte um PDF e retorna o Markdown (não grava o .md em disco)."""
    with pymupdf.open(pdf) as doc:
        pages = parse_pages(opts.pages, doc.page_count)

    if opts.engine == "docling":
        return _convert_docling(pdf, pages, opts)

    if not has_text_layer(pdf, pages):
        raise ScannedPdfError(
            "O PDF parece escaneado (não tem texto selecionável). "
            "Use o motor Docling com OCR.")
    if opts.engine == "markitdown":
        return _convert_markitdown(pdf, pages)
    return _convert_pymupdf4llm(pdf, pages, opts)


# ---------------- PyMuPDF4LLM ----------------
def _convert_pymupdf4llm(pdf: Path, pages, opts: ConvertOptions) -> str:
    import pymupdf4llm  # import pesado (layout + onnxruntime): só quando usado
    kwargs = {"pages": pages, "show_progress": False}
    if opts.write_images:
        img_dir = image_dir_for(pdf, opts)
        img_dir.mkdir(parents=True, exist_ok=True)
        kwargs.update(write_images=True, image_path=str(img_dir))
    with pymupdf.open(pdf) as doc:
        return pymupdf4llm.to_markdown(doc, **kwargs)


# ---------------- MarkItDown ----------------
_markitdown = None


def _convert_markitdown(pdf: Path, pages) -> str:
    global _markitdown
    from markitdown import MarkItDown
    if _markitdown is None:
        _markitdown = MarkItDown(enable_plugins=False)
    with _subset(pdf, pages) as src:
        return _markitdown.convert(str(src)).text_content


# ---------------- Docling ----------------
_docling_cache: dict[tuple, object] = {}
_docling_lock = threading.Lock()


def _docling_converter(ocr: str, images: bool):
    key = (ocr, images)
    with _docling_lock:
        if key not in _docling_cache:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import OcrAutoOptions, PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            po = PdfPipelineOptions(
                do_ocr=ocr != "off",
                ocr_options=OcrAutoOptions(force_full_page_ocr=ocr == "force"),
                generate_picture_images=images,
                images_scale=2.0 if images else 1.0,
            )
            _docling_cache[key] = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=po)})
        return _docling_cache[key]


def _convert_docling(pdf: Path, pages, opts: ConvertOptions) -> str:
    from docling_core.types.doc.base import ImageRefMode

    conv = _docling_converter(opts.ocr, opts.write_images)
    # Docling aceita só intervalo contínuo; para seleções com saltos, recorta o PDF.
    contiguous = pages is None or pages == list(range(pages[0], pages[-1] + 1))
    if contiguous:
        rng = (1, 2**62) if pages is None else (pages[0] + 1, pages[-1] + 1)
        doc = conv.convert(pdf, page_range=rng).document
    else:
        with _subset(pdf, pages) as src:
            doc = conv.convert(src).document

    kwargs = {"escape_html": False}
    if opts.write_images:
        img_dir = image_dir_for(pdf, opts)
        img_dir.mkdir(parents=True, exist_ok=True)
        kwargs.update(image_mode=ImageRefMode.REFERENCED, image_dir=img_dir,
                      image_uri_prefix=img_dir.name + "/")
    return doc.export_to_markdown(**kwargs)


# ---------------- util ----------------
class _subset:
    """Context manager: devolve o próprio PDF ou um PDF temporário só com as páginas pedidas."""

    def __init__(self, pdf: Path, pages):
        self.pdf, self.pages, self.tmp = pdf, pages, None

    def __enter__(self) -> Path:
        if self.pages is None:
            return self.pdf
        fd, name = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        self.tmp = Path(name)
        with pymupdf.open(self.pdf) as doc:
            doc.select(self.pages)
            doc.save(self.tmp)
        return self.tmp

    def __exit__(self, *exc):
        if self.tmp:
            self.tmp.unlink(missing_ok=True)
