[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "StemPlay Library"
Set-Location -Path $PSScriptRoot

try {
    $null = python --version 2>&1
} catch {
    Write-Host ""
    Write-Host "  [ERRO] Python nao encontrado!"
    Write-Host "  Baixe em: https://www.python.org/downloads/"
    Write-Host '  Marque "Add Python to PATH" na instalacao.'
    Write-Host ""
    Read-Host "Pressione Enter para sair."
    exit 1
}

$null = python -m pip install --upgrade pip 2>&1
$null = python -m pip install aiohttp tqdm qrcode pymupdf 2>&1

try {
    $null = python -c "import aiohttp" 2>&1
} catch {
    Write-Host "  [ERRO] Falha ao instalar dependencias."
    Read-Host "Pressione Enter para sair"
    exit 1
}

python launcher.py
Read-Host "Pressione Enter para sair"
