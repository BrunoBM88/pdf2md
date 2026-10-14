# Como contribuir

Obrigado pelo interesse! 🙌

Antes de tudo: **não sou programador.** Fiz o PDF2MD para resolver um problema meu, com ajuda de IA.
Então sugestões são bem-vindas, sejam de quem programa ou de quem só usa o programa, e paciência com
a minha demora para entender algumas coisas também. 😊

## Encontrou um problema ou tem uma ideia?

Abra uma [issue](../../issues/new/choose) e escolha **Reportar problema** ou **Sugerir recurso**.
Se o problema for com um PDF específico, **não anexe documentos com dados pessoais ou sigilosos**.
Descreva o tipo de documento (ex.: "nota fiscal escaneada, 2 páginas, com tabela").

## Rodando a partir do código

Pré-requisitos: Windows 10/11 e [Python 3.14](https://www.python.org/downloads/).

```bat
git clone https://github.com/BrunoBM88/pdf2md.git
cd pdf2md
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
PDF2MD.bat
```

## Gerando o `.exe`

```bat
.venv\Scripts\pip install pyinstaller==6.22.3
build.bat
```

O `build.bat` mostra uma barra de progresso e gera `dist\PDF2MD\PDF2MD.exe` (~1,1 GB, demora uns 15 minutos).
Para instalar a versão compilada no seu usuário: `installer\Instalar.bat`.

Ao publicar uma tag `v*` (ex.: `v1.0.1`), o GitHub Actions compila e anexa o `.zip` à Release
automaticamente (veja `.github/workflows/release.yml`).

## Estrutura do projeto

```
pdf2md/
  app.py               interface gráfica (PySide6), instância única, modo --cli
  converter.py         os três motores de conversão
  shell_integration.py menu do botão direito no Explorer (registro HKCU)
installer/             instalar/desinstalar por usuário (PowerShell)
tools/                 geração do ícone e das capturas de tela
docs/                  imagens do README e PDF de exemplo (Lorem ipsum)
PDF2MD.spec            receita do PyInstaller
build.ps1 / build.bat  build com barra de progresso
```

## Armadilhas conhecidas do build

- O **torchvision para Python 3.14** usa extensões `*_stable.pyd`, que o hook padrão do PyInstaller
  não inclui. O `PDF2MD.spec` adiciona esses arquivos manualmente.
- O **transformers** procura submódulos lendo os `.py` no disco, por isso o `.spec` usa
  `module_collection_mode={"transformers": "pyz+py"}`.
- O **pymupdf4llm** demora para importar (carrega o ONNX Runtime). Por isso ele só é importado na
  primeira conversão e é pré-carregado em segundo plano depois que a janela abre.

## Atualizando as capturas de tela

```bat
.venv\Scripts\python tools\make_screenshots.py
```

Use **sempre** o PDF de exemplo em `docs/exemplo/` (texto Lorem ipsum), nunca documentos reais, nem com nomes trocados.
