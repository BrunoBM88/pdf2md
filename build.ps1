# Compila o PDF2MD.exe mostrando uma barra de progresso.
# O percentual é estimado pelo nº de linhas do log, comparado com o build anterior.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$log = Join-Path $PSScriptRoot "build.log"
$ref = Join-Path $PSScriptRoot ".build_lines"
$expected = if (Test-Path $ref) { [int](Get-Content $ref) } else { 330 }

$stages = [ordered]@{
    "Analyzing"                 = "Analisando o código"
    "Processing module hooks"   = "Processando bibliotecas (Docling, PyTorch...)"
    "Looking for dynamic libr"  = "Procurando DLLs"
    "Building PYZ"              = "Empacotando módulos Python"
    "Building PKG"              = "Montando o pacote"
    "Building EXE"              = "Gerando PDF2MD.exe"
    "Building COLLECT"          = "Copiando arquivos para dist\PDF2MD (o mais demorado no fim)"
}

Remove-Item $log -ErrorAction SilentlyContinue
$p = Start-Process ".venv\Scripts\python.exe" -ArgumentList "-m", "PyInstaller", "PDF2MD.spec", "--noconfirm" `
     -RedirectStandardError $log -NoNewWindow -PassThru
$t0 = Get-Date
$stage = "Iniciando"
while (-not $p.HasExited) {
    Start-Sleep -Milliseconds 700
    $lines = @(Get-Content $log -ErrorAction SilentlyContinue)
    foreach ($l in $lines[-20..-1]) { foreach ($k in $stages.Keys) { if ($l -match $k) { $stage = $stages[$k] } } }
    $pct = [math]::Min(99, [int](100 * $lines.Count / $expected))
    $el = (Get-Date) - $t0
    Write-Progress -Activity "Compilando PDF2MD" -Status ("{0}%  -  {1}  -  {2:mm\:ss}" -f $pct, $stage, $el) -PercentComplete $pct
}
$p.WaitForExit()
Write-Progress -Activity "Compilando PDF2MD" -Completed
$total = @(Get-Content $log).Count
$el = (Get-Date) - $t0
if ($p.ExitCode -eq 0) {
    Set-Content $ref $total
    Write-Host ("Build concluído em {0:mm\:ss}: dist\PDF2MD\PDF2MD.exe" -f $el) -ForegroundColor Green
} else {
    Write-Host "Build falhou (código $($p.ExitCode)). Últimas linhas do build.log:" -ForegroundColor Red
    Get-Content $log -Tail 20
    exit 1
}
