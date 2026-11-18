"""Create the public cPanel upload ZIP only when requested by the owner."""
from pathlib import Path
import argparse,zipfile,hashlib
from public_files import ROOT,public_files
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT.parent/'csexitethiopia-upload.zip');args=parser.parse_args()
files=public_files();assert all(p.exists()for p in files);args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED)as archive:
 for p in files:archive.write(p,p.relative_to(ROOT))
 assert 'index.html'in archive.namelist()and not archive.testzip()
print('Archive:',args.output);print('Public files:',len(files));print('SHA256:',hashlib.sha256(args.output.read_bytes()).hexdigest())
