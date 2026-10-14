# Histórico de versões

Todas as mudanças importantes do PDF2MD ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-10-14

Primeira versão pública.

### Adicionado
- Interface gráfica com **arrastar e soltar** de PDFs e pastas, incluindo subpastas.
- **Três motores de conversão**: Rápido (PyMuPDF4LLM), Tabelas e layout + OCR (Docling) e Simples (MarkItDown).
- **OCR** para PDFs escaneados, via Docling + RapidOCR, com modos Automático, Forçar e Desligado.
- Aviso quando um PDF escaneado é aberto num motor sem OCR.
- **Prévia** com o Markdown formatado e o texto editável, e as edições são salvas.
- Botões separados: **Converter selecionado / todos** e **Salvar selecionado / todos**.
- Salvamento na **pasta de origem do PDF** por padrão, ou em outra pasta.
- Confirmação antes de substituir `.md` existentes e antes de descartar conversões não salvas.
- Escolha de **páginas** (ex.: `1-3, 5`) e extração de **imagens**.
- **Menu do botão direito** no Explorer para arquivos PDF e pastas.
- **Instância única**: vários arquivos enviados pelo Explorer caem na mesma janela.
- **Modo linha de comando** (`--cli`).
- Instalador por usuário (sem administrador), com atalho no Menu Iniciar e desinstalação pelas Configurações do Windows.
