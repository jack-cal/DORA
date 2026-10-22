# Third-party sources and licenses

The frozen English BIP39 wordlist retains its [upstream license](../app/src/main/python/assets/bip39/LICENSE)
and [source and hash record](../app/src/main/python/assets/bip39/SOURCES.json). Public BIP32/BIP39
verification vectors retain their [upstream license](../app/src/main/python/vectors/HD_STANDARD_VECTORS_LICENSE.txt).
SUMUWW's HD derivation and mnemonic implementation is application code; these
data files and standards retain their original attribution.

The Windows AMD64 / CPython 3.12 wheels were downloaded from official PyPI and checked against its published SHA-256 values. The [lock file](../docs/pc043/programs/PC/requirements-win-cp312.lock) requires matching hashes for every dependency. Source installations use a project-local `.deps` directory. Exact URLs, versions, hashes and license files are recorded in [dependency provenance](../app/src/main/python/docs/DEPENDENCY_PROVENANCE.json).

- [coincurve 21.0.0](https://pypi.org/project/coincurve/21.0.0/): [MIT](dependencies/LICENSE-MIT) or [Apache-2.0](dependencies/LICENSE-APACHE), [NOTICE](dependencies/NOTICE).
- [cryptography 50.0.1](https://pypi.org/project/cryptography/50.0.1/): [license](dependencies/cryptography-LICENSE), [Apache-2.0](dependencies/cryptography-LICENSE.APACHE), [BSD](dependencies/cryptography-LICENSE.BSD).
- [cffi 2.1.0](https://pypi.org/project/cffi/2.1.0/): [MIT](dependencies/cffi-LICENSE). The [license](dependencies/LICENSE-cffi) for the backend bundled by Coincurve is also retained.
- [pycparser 3.0](https://pypi.org/project/pycparser/3.0/): [BSD](dependencies/pycparser-LICENSE).
- [libsecp256k1](https://github.com/bitcoin-core/secp256k1): [MIT](dependencies/LICENSE-secp256k1). COPYING is retained for upstream ref `0cdc758a56360bf58a851fe91085a327ec97685a`, the declared [default build input](https://github.com/ofek/coincurve/blob/v21.0.0/pyproject.toml) for Coincurve v21.0.0.

Bech32 descriptions and validation vectors reference the BSD-2-Clause material in [BIP173](https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki). Code and tests cite the source. Official wheel hashes have been verified; this is not an independent binary rebuild attestation or completed security audit. SUMUWW application code uses the [MIT license](../docs/pc043/LICENSE); each dependency retains its own terms above.

The [MIT copyright and permission notice](dependencies/LICENSE-bech32-reference) for the Bech32 [reference implementation](https://github.com/sipa/bech32/blob/7a7d7ab158db7078a333384e0e918c90dbc42917/ref/python/segwit_addr.py) is also preserved. Its reference commit and original content hash are recorded in dependency provenance.

Noto Sans Arabic is distributed under the SIL Open Font License 1.1. Font and license: ../app/src/main/assets/fonts/NotoSansArabic.ttf and ../app/src/main/assets/fonts/OFL-NotoSansArabic.txt. Source: https://github.com/google/fonts/tree/main/ofl/notosansarabic
