"""Write complete checksums for an assembled desktop distribution."""
import argparse
import hashlib
import json
from pathlib import Path


def write(root):
    root = Path(root).resolve()
    excluded = {root / 'FILE_HASHES.json', root / 'SHA256SUMS.txt'}
    hashes = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path not in excluded:
            with path.open('rb') as stream:
                hashes[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    checksum = root / 'SHA256SUMS.txt'
    checksum.write_text(''.join(f'{digest}  {name}\n' for name, digest in hashes.items()), encoding='utf-8')
    with checksum.open('rb') as stream:
        hashes['SHA256SUMS.txt'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (root / 'FILE_HASHES.json').write_text(json.dumps(dict(sorted(hashes.items())), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return len(hashes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    print(f"Hashed {write(parser.parse_args().root)} files, including nested checksum files.")
