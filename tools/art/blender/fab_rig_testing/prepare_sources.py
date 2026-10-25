"""Unpack the two user-acquired archives as data, without launching Unity."""
from pathlib import Path
import zipfile,tarfile
ROOT=Path(__file__).resolve().parents[4];r=ROOT/'Local/FabRigTesting/Source'
def save(base,name,data):
 p=base/name
 if not p.resolve().is_relative_to(base.resolve()):raise ValueError('Unsafe archive path')
 if p.exists():
  if p.read_bytes()!=data:raise ValueError('Refusing to overwrite different source '+str(p))
  return
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
with zipfile.ZipFile(r/'Sword and Shield Pack.zip') as z:
 for n in z.namelist():
  if not n.endswith('/'):save(r/'Mixamo',n,z.read(n))
with tarfile.open(r/'freesampleanimationset.unitypackage') as t:
 members={m.name:m for m in t.getmembers()}
 for n,m in members.items():
  if n.endswith('/pathname'):
   path=t.extractfile(m).read().decode();asset=n.rsplit('/',1)[0]+'/asset'
   if asset in members:save(r/'Fab',path,t.extractfile(members[asset]).read())
print('Local source data ready; no marketplace or game mutation.')
