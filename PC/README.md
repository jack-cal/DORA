# SUMUWW Windows 0.57.34

Windows AMD64 full node, wallet and CPU miner. English is the default; all 34 UI languages remain available.

## Added and fixed

- Automatically prepare a fresh distributed-randomness key when the current beacon group cannot supply enough valid responses.
- Check participant health with authenticated threshold shares; retry withheld or invalid DKG contributions and unavailable prepared proposals.
- Bind each replacement to its exact predecessor and a round on the same PoW ancestry. Nodes independently validate the public setup and readiness signatures.
- Preserve completed historical proofs under their original key. Recovery does not block PoW mining or redraw old proof jobs.
- Preserve wallets, valid historical blocks, issuance, halvings, the 20% random event probability, cumulative-work priority and DGW/10 from height 9000.

- Show the scheduled height-9000 transition in all 34 languages: per-block DGW before activation, then adjustment every ten blocks.
- Correct Windows executable file-version metadata to 0.57.34 and reject stale version resources during builds.

## Verification

Eight independent process identities tested withholding, replacement, restart and late verification. Ten new recovery regression cases passed. The PC regression run passed 28 distinct cases across 36 executions, plus two numeric activation-prefix cases. Four UI/catalog tests covered all 34 languages. Six packaged executable checks passed after rebuilding.

## Download and update

[Windows ZIP](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.34/SUMUWW-PC-0.57.34-English.zip) · [Windows source ZIP](https://github.com/jack-cal/SUMUWW/releases/download/pc-v0.57.34/SUMUWW-Windows-Source-0.57.34-English.zip)

Extract the complete archive, close the previous program, and run SUMUWW.exe using the existing data directory. Keep the encrypted wallet and node database. The complete portable runtime is included; a separate Python installation is unnecessary. Windows executables do not have a publisher code-signing certificate. Check PC-SHA256SUMS.txt on the release page.

## Compatibility and scope

Recovery requires at least three usable participants, eventual delivery and a mined commitment. Old incomplete jobs may remain incomplete if their original threshold shares are lost. Validating nodes must upgrade before new recovery records are used. The protocol remains experimental; local checks are not an independent cryptographic audit or a multi-day public-network trial.

[Source](Source) · [Recovery protocol](../Documentation/BEACON_RECOVERY.md) · [Verification](../Documentation/BEACON_RECOVERY_VERIFICATION.md)
