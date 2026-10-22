$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = if ($env:SMW_BUILD_PYTHON) { $env:SMW_BUILD_PYTHON } else { '.venv/Scripts/python.exe' }
& $taskPython -m PyInstaller --noconfirm --clean --onedir --windowed --name SUMUWW-P2P --paths vendor --add-data 'tools/bitcoin-31.1;tools/bitcoin-31.1' --add-data 'tools/runtime-manifest.json;tools' --add-data 'smw_trade/locales;smw_trade/locales' --add-data 'assets/fonts;assets/fonts' --collect-all coincurve --collect-submodules py_ecc --collect-submodules nacl --distpath dist-native --workpath build-native run.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
