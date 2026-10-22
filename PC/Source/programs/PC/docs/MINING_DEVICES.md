# CPU / GPU / ASIC

CPU is always available. GPU becomes selectable at verified active-chain height 12,000; ASIC at 12,000. This is an official-program policy, not a consensus restriction on hardware. GPU requires an accessible OpenCL GPU driver. ASIC uses a local solo Stratum V1 listener and pays the selected wallet directly. It does not distribute pooled shares. Stop mining before changing devices. A chain reorganization below the unlock height blocks the selected device until the height recovers or CPU is selected.

GPU: OpenCL

ASIC: `stratum+tcp://<local-node-ip>:3333`

Worker: `sumuww`

Connection password: 16–128 characters. Set the same password in the app and ASIC device.

Only block-target proof of work is accepted. No automatic public port opening. Model-specific ASIC firmware compatibility requires testing with the actual device.
