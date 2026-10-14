# Instala o PDF2MD para o usuário atual (sem precisar de administrador).
# - copia dist\PDF2MD para %LOCALAPPDATA%\Programs\PDF2MD
# - cria atalhos no Menu Iniciar (e na Área de Trabalho, se pedido)
# - adiciona "Converter para Markdown (PDF2MD)" ao botão direito em PDFs e pastas
param([switch]$Desktop)
$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "..\dist\PDF2MD"
if (-not (Test-Path "$src\PDF2MD.exe")) { $src = Join-Path $PSScriptRoot "PDF2MD" }   # pacote distribuído
if (-not (Test-Path "$src\PDF2MD.exe")) { throw "PDF2MD.exe não encontrado. Rode o build antes." }

$dest = Join-Path $env:LOCALAPPDATA "Programs\PDF2MD"
$exe  = Join-Path $dest "PDF2MD.exe"

Get-Process PDF2MD -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Copiando arquivos para $dest ..."
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item "$src\*" $dest -Recurse -Force
Copy-Item (Join-Path $PSScriptRoot "uninstall.ps1") $dest -Force

# atalhos
$shell = New-Object -ComObject WScript.Shell
function New-Shortcut($path) {
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = $exe
    $s.WorkingDirectory = $dest
    $s.IconLocation = "$exe,0"
    $s.Description = "Converter PDF para Markdown"
    $s.Save()
}
New-Shortcut (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\PDF2MD.lnk")
if ($Desktop) { New-Shortcut (Join-Path ([Environment]::GetFolderPath("Desktop")) "PDF2MD.lnk") }

# menu do botão direito (HKCU = só este usuário)
foreach ($key in @(
    "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\PDF2MD",
    "HKCU:\Software\Classes\Directory\shell\PDF2MD")) {
    New-Item -Path "$key\command" -Force | Out-Null
    Set-ItemProperty -Path $key -Name "(default)" -Value "Converter para Markdown (PDF2MD)"
    Set-ItemProperty -Path $key -Name "Icon" -Value "`"$exe`""
    Set-ItemProperty -Path $key -Name "MultiSelectModel" -Value "Player"
    Set-ItemProperty -Path "$key\command" -Name "(default)" -Value "`"$exe`" `"%1`""
}

# entrada em "Aplicativos instalados" para desinstalar pelo Windows
$un = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF2MD"
New-Item -Path $un -Force | Out-Null
Set-ItemProperty $un DisplayName "PDF2MD - PDF para Markdown"
Set-ItemProperty $un DisplayIcon "`"$exe`""
Set-ItemProperty $un InstallLocation $dest
Set-ItemProperty $un Publisher "PDF2MD"
Set-ItemProperty $un DisplayVersion "1.0.0"
Set-ItemProperty $un UninstallString "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$dest\uninstall.ps1`""
Set-ItemProperty $un NoModify 1 -Type DWord
Set-ItemProperty $un NoRepair 1 -Type DWord

Write-Host ""
Write-Host "PDF2MD instalado em $dest" -ForegroundColor Green
Write-Host "Menu Iniciar: PDF2MD | Botão direito em PDF/pasta: 'Converter para Markdown (PDF2MD)'"
Write-Host "(No Windows 11 o item aparece em 'Mostrar mais opções' ou Shift+F10.)"
