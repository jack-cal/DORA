# SUMUWW release workflow

- When behavior or functionality changes, increment the affected application versions, rebuild and verify the packages, then update the canonical desktop distribution and its matching source archives, documentation and checksums. Do not call an old binary the latest build.
- Ask the user before any GitHub publication. Publish only after explicit approval for that upload; a previous upload approval does not authorize later releases.
- Publish release descriptions, primary documentation and technical documents in English. Retain all 34 UI languages and saved language preferences.
- Preserve existing wallets, coins and valid chain history. Do not package personal wallets, chain databases, signing keys or raw device/network logs.
- Report unresolved issues and the limits of verification accurately. Do not present a short test as uninterrupted network availability.

- Keep English as the default. Apply documentation corrections to every supported UI language (currently 34); author translations directly without external automatic translation. Record the exact translated scope and keep language links local to that edition.
