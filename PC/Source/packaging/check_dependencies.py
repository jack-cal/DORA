"""Reject a Windows build whose runtime pins differ from the build environment."""
import importlib.metadata
from pathlib import Path
import re


def check(source):
    source = Path(source)
    def pins(path):
        result = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)(?:\s|$)', line)
            if not match:
                raise RuntimeError(f'Unpinned runtime dependency in {path.name}: {line}')
            result[re.sub(r'[-_.]+', '-', match[1]).lower()] = match[2]
        return result
    expected = pins(source / 'requirements.txt')
    locked = pins(source / 'requirements-win-cp312.lock')
    if not expected or expected != locked:
        raise RuntimeError('Windows requirements and hash lock must list the same versions')
    for name, version in expected.items():
        actual = importlib.metadata.version(name)
        if actual != version:
            raise RuntimeError(f'Build dependency mismatch: {name} requires {version}, found {actual}')
    return expected


if __name__ == '__main__':
    print(f'Checked {len(check(Path(__file__).resolve().parents[1]))} runtime dependency versions.')
