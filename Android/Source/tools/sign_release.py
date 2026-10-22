"""Sign official updates using private keys outside the public source tree.

Set SUMUWW_SIGNING_DIR and ANDROID_SDK_ROOT. Nothing in this script generates or
exports private keys. Local Gradle compatible builds remain development builds.
"""
import argparse
import os
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('apk',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
directory=Path(os.environ.get('SUMUWW_SIGNING_DIR') or os.environ['DORA_SIGNING_DIR']).resolve()
sdk=Path(os.environ['ANDROID_SDK_ROOT'])
tool=sdk/'build-tools/35.0.0/apksigner.bat'
keyfile=directory/'sumuww-release.p12'
if not keyfile.is_file():keyfile=directory/'dora-release.p12'
for name in ('legacy.keystore','password.txt','lineage.bin'):
    if not (directory/name).is_file():raise RuntimeError('Missing private signing configuration: '+name)
if not keyfile.is_file():raise RuntimeError('Missing private release signing key')
subprocess.run([str(tool),'sign','--ks',str(directory/'legacy.keystore'),
 '--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android',
 '--next-signer','--ks',str(keyfile),'--ks-key-alias','dora',
 '--ks-pass','file:'+str(directory/'password.txt'),'--lineage',str(directory/'lineage.bin'),
 '--rotation-min-sdk-version','28','--v4-signing-enabled','false','--out',str(args.output),str(args.apk)],check=True)
subprocess.run([str(tool),'verify','--verbose',str(args.output)],check=True)
