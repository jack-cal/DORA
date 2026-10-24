# SUMUWW Whitepaper v2.2 — English

Release edition, 24 October 2026. Download: https://github.com/jack-cal/SUMUWW/releases/tag/whitepaper-v2.2-en.

- Align witness selection with PC 0.57.40 / Android 0.6.89: probe all discovered identities, then sample three responsive identities with the verified beacon.
- Distinguish the signed availability probe from the BLS beacon-health challenge and from consensus membership.
- Explain saved partial replies, diagnostic phases, retries and preservation of original messages and witnesses for already selected jobs.
- Define setup, lottery, selected-pending, selected-complete and stored-proof counters; explain why 11 minus 9 does not imply two completed proofs.
- Distinguish full validation, wallet-only recent activity, public active-chain history and Explorer's transaction-inclusion proofs.
- Separate published downloads, local prepared documents and historical test evidence. Retain the original recovery verification in a dated record.
- Retain issuance, halvings, 20% event probability, three-signature format, cumulative-work-first selection, DGW/10 and height-9100 HTLC rules.

## Previous edition: v2.1, published 22 October 2026

Added fresh-key beacon-generation recovery, predecessor/ancestor-round binding,
twelve-block spacing and historical-proof preservation. That edition predates
the responsive-witness and partial-reply repair. Its published archive and
checksums remain unchanged. This documentation is not an independent security audit.
