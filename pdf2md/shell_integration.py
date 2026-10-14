"""Menu de contexto do Windows Explorer (só para o usuário atual, HKCU)."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

MENU_TEXT = "Converter para Markdown (PDF2MD)"
KEYS = [
    r"Software\Classes\SystemFileAssociations\.pdf\shell\PDF2MD",  # arquivos .pdf
    r"Software\Classes\Directory\shell\PDF2MD",                    # pastas
]


def launch_command() -> tuple[str, str]:
    """(comando com %1, ícone) para o programa atual: .exe ou pythonw + run.pyw."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return f'"{exe}" "%1"', str(exe)
    root = Path(__file__).resolve().parent.parent
    pyw = Path(sys.executable).with_name("pythonw.exe")
    icon = root / "assets" / "pdf2md.ico"
    return f'"{pyw}" "{root / "run.pyw"}" "%1"', str(icon if icon.exists() else pyw)


def is_registered() -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEYS[0]))
        return True
    except OSError:
        return False


def register() -> None:
    cmd, icon = launch_command()
    for key in KEYS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, MENU_TEXT)
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
            # permite enviar vários arquivos selecionados de uma vez
            winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)


def unregister() -> None:
    for key in KEYS:
        for sub in (key + r"\command", key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    # uso: python -m pdf2md.shell_integration [install|uninstall]
    (unregister if sys.argv[1:] == ["uninstall"] else register)()
    print("registrado" if is_registered() else "removido")
