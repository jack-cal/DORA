"""Sign the Current wallet using private configuration outside the source tree."""
import argparse
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('apk', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
private = Path(os.environ['SUMUWW_WALLET_SIGNING_DIR'])
tool = Path(os.environ['ANDROID_SDK_ROOT']) / 'build-tools/35.0.0/apksigner.bat'
for name in ('wallet-current.p12', 'password.txt'):
    if not (private / name).is_file():
        raise RuntimeError('Private wallet signing configuration is missing')
subprocess.run([str(tool), 'sign', '--ks', str(private / 'wallet-current.p12'),
                '--ks-key-alias', 'sumuww-wallet-current', '--ks-pass',
                'file:' + str(private / 'password.txt'), '--v4-signing-enabled', 'false',
                '--out', str(args.output), str(args.apk)], check=True)
subprocess.run([str(tool), 'verify', '--verbose', '--print-certs', str(args.output)], check=True)
