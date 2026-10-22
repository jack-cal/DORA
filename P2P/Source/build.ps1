$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = if ($env:SMW_BUILD_PYTHON) { $env:SMW_BUILD_PYTHON } else { '.venv/Scripts/python.exe' }
& $taskPython -m PyInstaller --noconfirm --clean --distpath dist-native --workpath build-native SUMUWW-P2P.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& $taskPython -m PyInstaller --noconfirm --clean --distpath dist-native --workpath build-light SUMUWW-P2P-Light.spec
if ($LASTEXITCODE -ne 0) { throw 'Light build failed' }
