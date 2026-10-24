# Build SUMUWW for Windows AMD64

Use CPython 3.12 in a project-local virtual environment. Install the runtime
dependencies from `requirements-win-cp312.lock` with pip's `--require-hashes`.
The audited build used PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9.

```powershell
python -m venv .buildenv
.\.buildenv\Scripts\python.exe -m pip install --require-hashes -r requirements-win-cp312.lock
.\.buildenv\Scripts\python.exe -m pip install PyInstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
.\.buildenv\Scripts\python.exe packaging\build_windows.py --source . --build
.\.buildenv\Scripts\python.exe -m unittest discover -s tests
.\.buildenv\Scripts\python.exe packaging\build_smoke.py --bundle bin\SUMUWW
```

The source tree includes the audited Tk DLL, matching script library, license,
upstream hashes and one-line source patch in `vendor/tk-font-quality`.
Its README explains how to rebuild that dependency. No system DLL or font
installation is required. Build logs and intermediate files stay under `build`.

The build also creates `SUMUWW-node-manager.exe`, which displays the running
SUMUWW peers independently through discovery and direct P2P queries. Keep it, `SUMUWW.exe`, `SUMUWW-node.exe`,
`_internal`, documents, launchers and licenses together.
Generate fresh SHA-256 manifests for the files actually included in a ZIP.
The supplied verification reports describe the supplied release, not a future
custom rebuild; rerun the checks and record the hashes of that rebuild.

Both the full-node builder and the wallet specification reject dependency
versions that differ from the requirements and hash lock. Android uses its
own ABI-specific pins, which are not replaced by this Windows lock.
