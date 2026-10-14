# Remove o PDF2MD do usuário atual.
$ErrorActionPreference = "SilentlyContinue"
$dest = Join-Path $env:LOCALAPPDATA "Programs\PDF2MD"

Get-Process PDF2MD | Stop-Process -Force
Remove-Item "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\PDF2MD" -Recurse -Force
Remove-Item "HKCU:\Software\Classes\Directory\shell\PDF2MD" -Recurse -Force
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PDF2MD" -Recurse -Force
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\PDF2MD.lnk") -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath("Desktop")) "PDF2MD.lnk") -Force

# a pasta não pode ser apagada pelo script que está dentro dela; agenda a remoção
Start-Process cmd.exe -ArgumentList "/c timeout /t 2 >nul & rmdir /s /q `"$dest`"" -WindowStyle Hidden
Write-Host "PDF2MD removido." -ForegroundColor Green
