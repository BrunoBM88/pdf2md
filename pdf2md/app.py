"""Interface gráfica do PDF2MD."""
from __future__ import annotations

import getpass
import json
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QFont, QGuiApplication, QIcon, QPainter
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSplitter, QStatusBar, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from . import __version__, shell_integration
from .converter import ENGINES, OCR_MODES, ConvertOptions, ScannedPdfError, convert, output_path_for

APP_NAME = "PDF2MD"
ROLE_PATH = Qt.UserRole        # caminho do PDF
ROLE_MD = Qt.UserRole + 1      # markdown convertido (pode ter sido editado)
ROLE_STATE = Qt.UserRole + 2   # estado do item (ver ICONS)
ROLE_INFO = Qt.UserRole + 3    # texto extra para o tooltip

ICONS = {"": "", "busy": "⏳ ", "converted": "◎ ", "saved": "✔ ", "error": "✖ "}


class Worker(QObject):
    """Converte uma lista de PDFs em segundo plano (não grava nada)."""
    file_started = Signal(int)               # índice
    file_done = Signal(int, str, float)      # índice, markdown, segundos
    file_failed = Signal(int, str)           # índice, mensagem
    finished = Signal()

    def __init__(self, jobs: list[tuple[int, Path]], opts: ConvertOptions):
        super().__init__()
        self.jobs, self.opts = jobs, opts
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for idx, pdf in self.jobs:
            if self._stop:
                break
            self.file_started.emit(idx)
            t0 = time.perf_counter()
            try:
                self.file_done.emit(idx, convert(pdf, self.opts), time.perf_counter() - t0)
            except ScannedPdfError as e:
                self.file_failed.emit(idx, str(e))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.file_failed.emit(idx, f"{type(e).__name__}: {e}")
        self.finished.emit()


class DropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)

    def dragEnterEvent(self, e: QDragEnterEvent):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dropEvent(self, e: QDropEvent):
        self.files_dropped.emit([u.toLocalFile() for u in e.mimeData().urls()])
        e.acceptProposedAction()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.count() == 0:
            p = QPainter(self.viewport())
            p.setPen(Qt.gray)
            p.drawText(self.viewport().rect(), Qt.AlignCenter | Qt.TextWordWrap,
                       "Arraste PDFs ou pastas aqui\nou clique em “Adicionar”")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME + " — PDF para Markdown")
        self.resize(1200, 800)
        self.settings = QSettings("PDF2MD", "PDF2MD")
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self._loading = False   # evita tratar o carregamento da prévia como edição

        # ---- painel esquerdo: arquivos ----
        self.list = DropList()
        self.list.files_dropped.connect(self.add_paths)
        self.list.currentItemChanged.connect(self.show_item)
        self.list.itemSelectionChanged.connect(self.update_buttons)

        self.btn_add = QPushButton("Adicionar PDFs…", clicked=self.pick_files)
        self.btn_folder = QPushButton("Adicionar pasta…", clicked=self.pick_folder)
        self.btn_remove = QPushButton("Remover", clicked=self.remove_selected)
        self.btn_clear = QPushButton("Limpar", clicked=self.clear_list)
        files_grid = QGridLayout()
        files_grid.addWidget(self.btn_add, 0, 0)
        files_grid.addWidget(self.btn_folder, 0, 1)
        files_grid.addWidget(self.btn_remove, 1, 0)
        files_grid.addWidget(self.btn_clear, 1, 1)

        # ---- opções ----
        self.engine = QComboBox()
        for key, label in ENGINES.items():
            self.engine.addItem(label, key)
        self.engine.setItemData(0, "Bom para PDFs de texto comuns. Converte em segundos.", Qt.ToolTipRole)
        self.engine.setItemData(1, "Melhor para tabelas (AFs, editais, notas). Lê PDFs escaneados com OCR. "
                                   "Mais lento: de segundos a minutos por arquivo.", Qt.ToolTipRole)
        self.engine.setItemData(2, "Extrai só o texto, sem tabelas nem títulos.", Qt.ToolTipRole)
        self._select(self.engine, self.settings.value("engine", "pymupdf4llm", str))

        self.ocr = QComboBox()
        for key, label in OCR_MODES.items():
            self.ocr.addItem(label, key)
        self._select(self.ocr, self.settings.value("ocr", "auto", str))
        self.ocr_label = QLabel("OCR:")
        self.engine.currentIndexChanged.connect(self.update_engine_ui)

        self.pages = QLineEdit()
        self.pages.setPlaceholderText("Todas (ex.: 1-3, 5)")
        self.images = QCheckBox("Extrair imagens")
        self.images.setChecked(self.settings.value("images", False, bool))

        self.same_folder = QCheckBox("Salvar na pasta de origem do PDF")
        self.same_folder.setChecked(True)  # padrão sempre: pasta de origem
        self.out_dir = QLineEdit()
        self.out_dir.setPlaceholderText("Outra pasta de saída")
        self.btn_out = QPushButton("…", clicked=self.pick_out_dir)
        self.btn_out.setFixedWidth(32)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_dir)
        out_row.addWidget(self.btn_out)
        self.same_folder.toggled.connect(self.update_out_ui)

        # ---- ações ----
        self.btn_conv_sel = QPushButton("Converter selecionado", clicked=self.convert_selected)
        self.btn_conv_all = QPushButton("Converter todos", clicked=self.convert_all)
        self.btn_save_sel = QPushButton("Salvar selecionado", clicked=self.save_selected)
        self.btn_save_all = QPushButton("Salvar todos", clicked=self.save_all)
        for b in (self.btn_conv_sel, self.btn_conv_all, self.btn_save_sel, self.btn_save_all):
            b.setMinimumHeight(34)
        for b in (self.btn_conv_sel, self.btn_conv_all):
            f = b.font(); f.setBold(True); b.setFont(f)
        actions_grid = QGridLayout()
        actions_grid.addWidget(self.btn_conv_sel, 0, 0)
        actions_grid.addWidget(self.btn_conv_all, 0, 1)
        actions_grid.addWidget(self.btn_save_sel, 1, 0)
        actions_grid.addWidget(self.btn_save_all, 1, 1)

        self.btn_cancel = QPushButton("Cancelar conversão", clicked=self.cancel)
        self.btn_cancel.setEnabled(False)
        self.progress = QProgressBar()

        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Arquivos</b>"))
        left.addWidget(self.list, 1)
        left.addWidget(QLabel("<small>◎ convertido · ✔ salvo · ✖ erro</small>"))
        left.addLayout(files_grid)
        left.addSpacing(8)
        left.addWidget(QLabel("<b>Conversão</b>"))
        left.addWidget(QLabel("Motor:"))
        left.addWidget(self.engine)
        left.addWidget(self.ocr_label)
        left.addWidget(self.ocr)
        left.addWidget(QLabel("Páginas:"))
        left.addWidget(self.pages)
        left.addWidget(self.images)
        left.addSpacing(8)
        left.addWidget(QLabel("<b>Salvar em</b>"))
        left.addWidget(self.same_folder)
        left.addLayout(out_row)
        left.addSpacing(8)
        left.addLayout(actions_grid)
        left.addWidget(self.btn_cancel)
        left.addWidget(self.progress)
        left_w = QWidget(); left_w.setLayout(left)

        # ---- painel direito: prévia ----
        self.raw = QPlainTextEdit()
        self.raw.setFont(QFont("Consolas", 10))
        self.raw.setLineWrapMode(QPlainTextEdit.NoWrap)  # tabelas Markdown ficam legíveis
        self.raw.setPlaceholderText("Selecione um arquivo e clique em “Converter selecionado”.")
        self.raw.textChanged.connect(self.on_text_edited)
        self.rendered = QTextBrowser()
        self.rendered.setOpenExternalLinks(True)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.rendered, "Visualizado")
        self.tabs.addTab(self.raw, "Markdown (editável)")

        self.preview_title = QLabel()
        btn_save_as = QPushButton("Salvar como…", clicked=self.save_as)
        btn_copy = QPushButton("Copiar", clicked=self.copy_current)
        bottom = QHBoxLayout()
        bottom.addWidget(self.preview_title, 1)
        bottom.addWidget(btn_copy)
        bottom.addWidget(btn_save_as)

        right = QVBoxLayout()
        right.addWidget(self.tabs, 1)
        right.addLayout(bottom)
        right_w = QWidget(); right_w.setLayout(right)

        split = QSplitter()
        split.addWidget(left_w)
        split.addWidget(right_w)
        split.setSizes([380, 820])
        self.setCentralWidget(split)
        self.setStatusBar(QStatusBar())

        tools = self.menuBar().addMenu("&Ferramentas")
        self.act_shell = QAction("Mostrar no menu do botão direito do Explorer", self, checkable=True)
        self.act_shell.setChecked(shell_integration.is_registered())
        self.act_shell.toggled.connect(self.toggle_shell)
        tools.addAction(self.act_shell)
        tools.addSeparator()
        tools.addAction(QAction("Sair", self, shortcut="Ctrl+Q", triggered=self.close))
        help_menu = self.menuBar().addMenu("A&juda")
        help_menu.addAction(QAction("Sobre o PDF2MD", self, triggered=self.about))
        self.setAcceptDrops(True)
        self.update_engine_ui()
        self.update_out_ui(self.same_folder.isChecked())
        self.update_buttons()

    def toggle_shell(self, on: bool):
        try:
            shell_integration.register() if on else shell_integration.unregister()
            self.statusBar().showMessage(
                "Menu do botão direito ativado (no Windows 11, fica em “Mostrar mais opções”)." if on
                else "Menu do botão direito removido.", 8000)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"Não foi possível alterar o menu de contexto:\n{e}")

    def about(self):
        QMessageBox.about(self, "Sobre o PDF2MD", (
            f"<h3>PDF2MD {__version__}</h3>"
            "<p>Converte PDFs em Markdown com uma interface gráfica simples.</p>"
            "<p>Não sou programador: fiz este programa para resolver o meu próprio problema "
            "de transformar PDFs em Markdown sem precisar de linha de comando.</p>"
            "<p>Motores: PyMuPDF4LLM, Docling (IBM) e MarkItDown (Microsoft).<br>"
            "Licença: AGPL-3.0</p>"))

    def receive_paths(self, paths: list[str]):
        """Arquivos enviados por outra instância (ex.: menu do botão direito)."""
        self.add_paths(paths)
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.show(); self.raise_(); self.activateWindow()

    # ---------- utilidades de UI ----------
    @staticmethod
    def _select(combo: QComboBox, key: str):
        i = combo.findData(key)
        if i >= 0:
            combo.setCurrentIndex(i)

    def update_engine_ui(self):
        docling = self.engine.currentData() == "docling"
        self.ocr.setVisible(docling)
        self.ocr_label.setVisible(docling)

    def update_out_ui(self, same: bool):
        self.out_dir.setDisabled(same)
        self.btn_out.setDisabled(same)

    def update_buttons(self):
        busy = self.thread is not None
        items = self.all_items()
        selected = self.list.selectedItems()
        for b in (self.btn_add, self.btn_folder, self.btn_remove, self.btn_clear):
            b.setEnabled(not busy)
        self.btn_conv_sel.setEnabled(not busy and bool(selected))
        self.btn_conv_all.setEnabled(not busy and bool(items))
        self.btn_save_sel.setEnabled(not busy and any(it.data(ROLE_MD) for it in selected))
        self.btn_save_all.setEnabled(not busy and any(it.data(ROLE_MD) for it in items))
        n = len(selected)
        self.btn_conv_sel.setText("Converter selecionados" if n > 1 else "Converter selecionado")
        self.btn_save_sel.setText("Salvar selecionados" if n > 1 else "Salvar selecionado")
        self.btn_cancel.setEnabled(busy)

    def all_items(self) -> list[QListWidgetItem]:
        return [self.list.item(i) for i in range(self.list.count())]

    def set_state(self, it: QListWidgetItem, state: str, info: str | None = None):
        it.setData(ROLE_STATE, state)
        if info is not None:
            it.setData(ROLE_INFO, info)
        it.setText(ICONS[state] + Path(it.data(ROLE_PATH)).name)
        extra = it.data(ROLE_INFO)
        it.setToolTip(it.data(ROLE_PATH) + (f"\n{extra}" if extra else ""))

    # ---------- arquivos ----------
    def add_paths(self, paths):
        existing = {it.data(ROLE_PATH) for it in self.all_items()}
        added = 0
        for p in map(Path, paths):
            pdfs = sorted(p.rglob("*.pdf")) if p.is_dir() else [p]
            for pdf in pdfs:
                if pdf.suffix.lower() != ".pdf" or str(pdf) in existing:
                    continue
                it = QListWidgetItem()
                it.setData(ROLE_PATH, str(pdf))
                self.set_state(it, "")
                self.list.addItem(it)
                existing.add(str(pdf))
                added += 1
        self.statusBar().showMessage(f"{added} arquivo(s) adicionado(s).", 4000)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self.update_buttons()

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Escolher PDFs", self.settings.value("last_dir", ""), "PDF (*.pdf)")
        if files:
            self.settings.setValue("last_dir", str(Path(files[0]).parent))
            self.add_paths(files)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Escolher pasta", self.settings.value("last_dir", ""))
        if d:
            self.settings.setValue("last_dir", d)
            self.add_paths([d])

    def pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Pasta de saída", self.out_dir.text())
        if d:
            self.out_dir.setText(d)

    def _confirm_discard(self, items) -> bool:
        pending = [it for it in items if it.data(ROLE_STATE) == "converted"]
        if not pending:
            return True
        return QMessageBox.question(
            self, APP_NAME, f"{len(pending)} arquivo(s) convertido(s) ainda não foram salvos. Remover mesmo assim?"
        ) == QMessageBox.Yes

    def remove_selected(self):
        sel = self.list.selectedItems()
        if self._confirm_discard(sel):
            for it in sel:
                self.list.takeItem(self.list.row(it))
        self.update_buttons()

    def clear_list(self):
        if self._confirm_discard(self.all_items()):
            self.list.clear()
            self.show_item(None)
        self.update_buttons()

    def dragEnterEvent(self, e):
        self.list.dragEnterEvent(e)

    def dropEvent(self, e):
        self.list.dropEvent(e)

    # ---------- opções ----------
    def options(self) -> ConvertOptions | None:
        out = None
        if not self.same_folder.isChecked():
            if not self.out_dir.text().strip():
                QMessageBox.warning(self, APP_NAME, "Escolha a outra pasta de saída ou marque “Salvar na pasta de origem do PDF”.")
                return None
            out = Path(self.out_dir.text().strip())
        self.settings.setValue("images", self.images.isChecked())
        self.settings.setValue("engine", self.engine.currentData())
        self.settings.setValue("ocr", self.ocr.currentData())
        return ConvertOptions(pages=self.pages.text(), write_images=self.images.isChecked(), output_dir=out,
                              engine=self.engine.currentData(), ocr=self.ocr.currentData())

    # ---------- conversão ----------
    def start(self, rows: list[int]):
        if self.thread or not rows:
            return
        opts = self.options()
        if opts is None:
            return
        jobs = [(r, Path(self.list.item(r).data(ROLE_PATH))) for r in rows]
        self.progress.setRange(0, len(jobs)); self.progress.setValue(0)
        self._ok = self._fail = 0
        self._engine_label = self.engine.currentText()

        self.thread = QThread()
        self.worker = Worker(jobs, opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.file_started.connect(self.on_started)
        self.worker.file_done.connect(self.on_done)
        self.worker.file_failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.thread.start()
        self.update_buttons()

    def convert_selected(self):
        self.start(sorted(self.list.row(it) for it in self.list.selectedItems()))

    def convert_all(self):
        self.start(list(range(self.list.count())))

    def cancel(self):
        if self.worker:
            self.worker.stop()
            self.statusBar().showMessage("Cancelando após o arquivo atual…")

    def on_started(self, idx):
        it = self.list.item(idx)
        self.set_state(it, "busy")
        msg = f"Convertendo {self.progress.value() + 1}/{self.progress.maximum()}: {Path(it.data(ROLE_PATH)).name}"
        if self.engine.currentData() == "docling":
            msg += "  (Docling pode levar alguns minutos)"
        self.statusBar().showMessage(msg)

    def on_done(self, idx, md, secs):
        it = self.list.item(idx)
        it.setData(ROLE_MD, md)
        self.set_state(it, "converted", f"Convertido com {self._engine_label} em {secs:.1f} s — ainda não salvo")
        if it is self.list.currentItem():
            self.show_item(it)
        self._ok += 1
        self.progress.setValue(self.progress.value() + 1)

    def on_failed(self, idx, msg):
        it = self.list.item(idx)
        it.setData(ROLE_MD, None)
        self.set_state(it, "error", f"Erro: {msg}")
        if it is self.list.currentItem():
            self.show_item(it)
        self._fail += 1
        self.progress.setValue(self.progress.value() + 1)

    def on_finished(self):
        self.thread.quit(); self.thread.wait()
        self.thread = self.worker = None
        # itens que ficaram em "⏳" por cancelamento voltam ao estado anterior
        for it in self.all_items():
            if it.data(ROLE_STATE) == "busy":
                self.set_state(it, "converted" if it.data(ROLE_MD) else "")
        msg = f"Conversão concluída: {self._ok} ok, {self._fail} com erro. Use “Salvar” para gravar os .md."
        self.statusBar().showMessage(msg)
        self.update_buttons()
        if self._fail:
            QMessageBox.warning(self, APP_NAME, msg + "\n\nPasse o mouse sobre os itens ✖ para ver o erro.")

    # ---------- salvar ----------
    def save_items(self, items: list[QListWidgetItem]):
        opts = self.options()
        if opts is None:
            return
        ready = [it for it in items if it.data(ROLE_MD)]
        skipped = len(items) - len(ready)
        if not ready:
            QMessageBox.information(self, APP_NAME, "Nenhum dos arquivos foi convertido ainda. Converta antes de salvar.")
            return
        targets = [(it, output_path_for(Path(it.data(ROLE_PATH)), opts)) for it in ready]
        existing = [t for _, t in targets if t.exists()]
        if existing:
            names = "\n".join(f"• {t.name}" for t in existing[:10]) + ("\n…" if len(existing) > 10 else "")
            if QMessageBox.question(self, APP_NAME, f"{len(existing)} arquivo(s) .md já existe(m):\n{names}\n\nSubstituir?"
                                    ) != QMessageBox.Yes:
                return
        saved, errors = 0, []
        for it, target in targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(it.data(ROLE_MD), encoding="utf-8")
                self.set_state(it, "saved", f"Salvo em {target}")
                saved += 1
            except OSError as e:
                errors.append(f"{target.name}: {e}")
        msg = f"{saved} arquivo(s) salvo(s)."
        if skipped:
            msg += f" {skipped} ignorado(s) por não estarem convertidos."
        self.statusBar().showMessage(msg, 8000)
        if errors:
            QMessageBox.warning(self, APP_NAME, msg + "\n\nErros:\n" + "\n".join(errors))
        if it := self.list.currentItem():
            self.show_item(it)

    def save_selected(self):
        self.save_items(self.list.selectedItems())

    def save_all(self):
        self.save_items(self.all_items())

    def save_as(self):
        text = self.raw.toPlainText()
        if not text:
            return
        it = self.list.currentItem()
        suggested = str(output_path_for(Path(it.data(ROLE_PATH)), self.options() or ConvertOptions())) if it else ""
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Markdown", suggested, "Markdown (*.md)")
        if path:
            Path(path).write_text(text, encoding="utf-8")
            if it:
                self.set_state(it, "saved", f"Salvo em {path}")
                self.show_item(it)
            self.statusBar().showMessage(f"Salvo em {path}", 5000)

    def copy_current(self):
        QGuiApplication.clipboard().setText(self.raw.toPlainText())
        self.statusBar().showMessage("Markdown copiado.", 3000)

    # ---------- prévia ----------
    def show_item(self, it, _prev=None):
        md = it.data(ROLE_MD) if it else None
        self._loading = True
        self.raw.setPlainText(md or "")
        self.rendered.setMarkdown(md or "")
        self._loading = False
        self.update_title(it)
        self.update_buttons()

    def update_title(self, it):
        if not it:
            self.preview_title.setText("")
        else:
            state = {"": "não convertido", "busy": "convertendo…", "converted": "convertido, não salvo",
                     "saved": "salvo", "error": "erro na conversão"}[it.data(ROLE_STATE)]
            self.preview_title.setText(f"<b>{Path(it.data(ROLE_PATH)).name}</b> — {state}")

    def on_text_edited(self):
        if self._loading:
            return
        text = self.raw.toPlainText()
        self.rendered.setMarkdown(text)
        it = self.list.currentItem()
        if it and it.data(ROLE_MD) is not None and text != it.data(ROLE_MD):
            it.setData(ROLE_MD, text)
            if it.data(ROLE_STATE) == "saved":
                self.set_state(it, "converted", "Editado — ainda não salvo")
                self.update_title(it)

    def closeEvent(self, e):
        pending = [it for it in self.all_items() if it.data(ROLE_STATE) == "converted"]
        if pending and QMessageBox.question(
                self, APP_NAME, f"{len(pending)} arquivo(s) convertido(s) não foram salvos. Sair mesmo assim?"
        ) != QMessageBox.Yes:
            e.ignore()
            return
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit(); self.thread.wait(3000)
        super().closeEvent(e)


SERVER_NAME = f"PDF2MD-{getpass.getuser()}"


def send_to_running(paths: list[str]) -> bool:
    """Tenta entregar os caminhos a uma janela já aberta. True se conseguiu."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(500):
        return False
    sock.write(json.dumps(paths).encode("utf-8"))
    sock.waitForBytesWritten(2000)
    sock.disconnectFromServer()
    return True


def run_cli(argv: list[str]) -> int:
    """PDF2MD.exe --cli arquivo.pdf [...] [--motor pymupdf4llm|docling|markitdown]
    [--ocr auto|force|off] [--paginas 1-3] [--saida pasta] [--imagens]
    Grava <nome>.md e um log em <saida ou pasta do PDF>/pdf2md_cli.log."""
    import argparse
    p = argparse.ArgumentParser(prog="PDF2MD --cli", exit_on_error=False)
    p.add_argument("pdfs", nargs="+")
    p.add_argument("--motor", default="pymupdf4llm", choices=list(ENGINES))
    p.add_argument("--ocr", default="auto", choices=list(OCR_MODES))
    p.add_argument("--paginas", default="")
    p.add_argument("--saida")
    p.add_argument("--imagens", action="store_true")
    a = p.parse_args(argv)
    opts = ConvertOptions(pages=a.paginas, write_images=a.imagens, engine=a.motor, ocr=a.ocr,
                          output_dir=Path(a.saida) if a.saida else None)
    log_lines, rc = [], 0
    for pdf in map(Path, a.pdfs):
        t0 = time.perf_counter()
        try:
            out = output_path_for(pdf, opts)
            out.parent.mkdir(parents=True, exist_ok=True)
            md = convert(pdf, opts)
            out.write_text(md, encoding="utf-8")
            log_lines.append(f"OK  {pdf.name} -> {out} ({len(md)} chars, {time.perf_counter() - t0:.1f} s)")
        except Exception as e:  # noqa: BLE001
            rc = 1
            log_lines.append(f"ERRO {pdf.name}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
    log = (Path(a.saida) if a.saida else Path(a.pdfs[0]).parent) / "pdf2md_cli.log"
    log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return rc


def main():
    if "--cli" in sys.argv:
        sys.exit(run_cli([x for x in sys.argv[1:] if x != "--cli"]))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets" / "pdf2md.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    paths = [str(Path(a).resolve()) for a in sys.argv[1:] if not a.startswith("-")]

    # Instância única: o Explorer abre um processo por arquivo selecionado.
    server = QLocalServer()
    for _ in range(20):
        if send_to_running(paths):
            return
        if server.listen(SERVER_NAME):
            break
        QLocalServer.removeServer(SERVER_NAME)  # resto de uma execução que travou
        time.sleep(0.1)

    w = MainWindow()

    def on_connection():
        sock = server.nextPendingConnection()
        buf = bytearray()

        def read():
            buf.extend(bytes(sock.readAll()))

        def done():
            read()
            try:
                w.receive_paths(json.loads(buf.decode("utf-8") or "[]"))
            finally:
                sock.deleteLater()

        sock.readyRead.connect(read)
        sock.disconnected.connect(done)

    server.newConnection.connect(on_connection)
    if paths:
        w.add_paths(paths)
    w.show()
    # pré-carrega o motor padrão em segundo plano para a 1ª conversão não esperar
    import threading
    threading.Thread(target=lambda: __import__("pymupdf4llm"), daemon=True).start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
