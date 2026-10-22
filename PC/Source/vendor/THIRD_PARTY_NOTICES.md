# Third-party sources and licenses

The frozen English BIP39 wordlist retains its [upstream license](../assets/bip39/LICENSE)
and [source and hash record](../assets/bip39/SOURCES.json). Public BIP32/BIP39
verification vectors retain their [upstream license](../vectors/HD_STANDARD_VECTORS_LICENSE.txt).
SUMUWW's HD derivation and mnemonic implementation is application code; these
data files and standards retain their original attribution.

The Windows AMD64 / CPython 3.12 wheels were downloaded from official PyPI and checked against its published SHA-256 values. The [lock file](../requirements-win-cp312.lock) requires matching hashes for every dependency. Source installations use a project-local `.deps` directory. Exact URLs, versions, hashes and license files are recorded in [dependency provenance](DEPENDENCY_PROVENANCE.json).

- [coincurve 21.0.0](https://pypi.org/project/coincurve/21.0.0/): [MIT](licenses/LICENSE-MIT) or [Apache-2.0](licenses/LICENSE-APACHE), [NOTICE](licenses/NOTICE).
- [cryptography 50.0.1](https://pypi.org/project/cryptography/50.0.1/): [license](licenses/cryptography-LICENSE), [Apache-2.0](licenses/cryptography-LICENSE.APACHE), [BSD](licenses/cryptography-LICENSE.BSD).
- [cffi 2.1.0](https://pypi.org/project/cffi/2.1.0/): [MIT](licenses/cffi-LICENSE). The [license](licenses/LICENSE-cffi) for the backend bundled by Coincurve is also retained.
- [pycparser 3.0](https://pypi.org/project/pycparser/3.0/): [BSD](licenses/pycparser-LICENSE).
- [libsecp256k1](https://github.com/bitcoin-core/secp256k1): [MIT](licenses/LICENSE-secp256k1). COPYING is retained for upstream ref `0cdc758a56360bf58a851fe91085a327ec97685a`, the declared [default build input](https://github.com/ofek/coincurve/blob/v21.0.0/pyproject.toml) for Coincurve v21.0.0.

Bech32 descriptions and validation vectors reference the BSD-2-Clause material in [BIP173](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki). Code and tests cite the source. Official wheel hashes have been verified; this is not an independent binary rebuild attestation or completed security audit. SUMUWW application code uses the [MIT license](../LICENSE); each dependency retains its own terms above.

The [MIT copyright and permission notice](licenses/LICENSE-bech32-reference) for the Bech32 [reference implementation](https://github.com/sipa/bech32/blob/7a7d7ab158db7078a333384e0e918c90dbc42917/ref/python/segwit_addr.py) is also preserved. Its reference commit and original content hash are recorded in dependency provenance.

The Windows GUI includes the SUMUWW-patched [Tk 8.6.12 font rendering build](tk-font-quality/README.md), with [upstream license](tk-font-quality/LICENSE.txt), [source patch](tk-font-quality/tkWinFont-quality.patch) and [source/build hashes](tk-font-quality/SOURCES.json). Its patch preserves font families, sizes and weights and explicitly selects ClearType rendering.

## Boundary runtime dependencies

- cytoolz 1.0.0: [cytoolz-LICENSE.txt](licenses/cytoolz-LICENSE.txt)
- eth-hash 0.8.0: [eth-hash-LICENSE](licenses/eth-hash-LICENSE)
- eth-typing 3.5.2: [eth-typing-LICENSE](licenses/eth-typing-LICENSE)
- eth-utils 2.3.1: [eth-utils-LICENSE](licenses/eth-utils-LICENSE)
- py-ecc 8.0.0: [py-ecc-LICENSE](licenses/py-ecc-LICENSE)
- PyNaCl 1.5.0: [PyNaCl-LICENSE](licenses/PyNaCl-LICENSE)
- toolz 1.2.0: [toolz-LICENSE.txt](licenses/toolz-LICENSE.txt)
- typing_extensions 4.16.0: [typing_extensions-LICENSE](licenses/typing_extensions-LICENSE)
