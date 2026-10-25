import json
from pathlib import Path
import tempfile
import unittest
from workspace.hint_alpha.bundled_references import resolve_bundled_references, copy_bundled_references, REFERENCE_VERSION
ROOT=Path(__file__).resolve().parents[1]

class BundledReferenceTests(unittest.TestCase):
 def test_shipped_packet_is_complete_and_copies_to_installed_layout(self):
  source,version,count=resolve_bundled_references(ROOT)
  self.assertEqual((version,count),(REFERENCE_VERSION,13))
  with tempfile.TemporaryDirectory() as tmp:
   self.assertEqual(copy_bundled_references(ROOT,tmp),(version,count))
   copied,_,_=resolve_bundled_references(tmp)
   self.assertEqual(source.read_bytes(),copied.read_bytes())
 def test_missing_corrupt_or_version_mismatched_assets_are_reported(self):
  for fault in ('missing','corrupt','version'):
   with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
    copy_bundled_references(ROOT,tmp)
    manifest,_,_=resolve_bundled_references(tmp);folder=manifest.parent
    metadata=json.loads((folder/'bundle.json').read_text());name=next(n for n in metadata['files'] if n.endswith('.png'))
    if fault=='missing':(folder/name).unlink()
    elif fault=='corrupt':(folder/name).write_bytes(b'broken')
    else:metadata['version']='old';(folder/'bundle.json').write_text(json.dumps(metadata))
    with self.assertRaises(ValueError):resolve_bundled_references(tmp)
 def test_pixel_hashes_match_existing_private_packet_contract(self):
  try:
   from PIL import Image
  except ImportError:self.skipTest('Pillow unavailable')
  import hashlib
  manifest,_,_=resolve_bundled_references(ROOT)
  for row in json.loads(manifest.read_text())['rows']:
   with Image.open(manifest.parent/row['crop']) as image:
    self.assertEqual(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest(),row['rgb_sha256'])

 def test_packaging_verifier_reads_bundled_assets_from_installed_site(self):
  import runpy,shutil
  verify=runpy.run_path(str(ROOT/'packaging/verify_payload.py'))['verify']
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);site=root/'runtime/Lib/site-packages'
   version,count=copy_bundled_references(ROOT,site)
   helper=site/'workspace/hint_alpha/bundled_references.py';helper.parent.mkdir(parents=True)
   shutil.copy2(ROOT/'workspace/hint_alpha/bundled_references.py',helper)
   dataset=site/'dataset/tiles_runtime_v0_2';(dataset/'labels.jsonl').write_text('');(dataset/'manifest.json').write_text('{}')
   build=dict(payload_sha256={},source_sha256={},label_sha256={'labels.jsonl':__import__('hashlib').sha256(b'').hexdigest()},template_sha256={},executor_enabled=False,project_version='test',reference_pack_version=version,reference_pack_count=count)
   (root/'BUILD_INFO.json').write_text(json.dumps(build));verify(root)
   build['reference_pack_count']=7;(root/'BUILD_INFO.json').write_text(json.dumps(build))
   with self.assertRaises(SystemExit):verify(root)

 def test_windows_autocrlf_checkout_preserves_all_bundle_bytes(self):
  import subprocess,shutil
  if not shutil.which('git'):self.skipTest('git unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   subprocess.run(['git','init','-q',str(root)],check=True)
   subprocess.run(['git','-C',str(root),'config','core.autocrlf','true'],check=True)
   shutil.copy2(ROOT/'.gitattributes',root/'.gitattributes')
   copy_bundled_references(ROOT,root)
   subprocess.run(['git','-C',str(root),'add','.gitattributes','dataset'],check=True,capture_output=True)
   folder=root/'dataset/tiles_runtime_v0_2/reference_pack'
   before={p.name:p.read_bytes() for p in folder.iterdir()}
   for path in folder.iterdir():path.unlink()
   subprocess.run(['git','-C',str(root),'checkout-index','-a','-f'],check=True,capture_output=True)
   self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})
   self.assertEqual(resolve_bundled_references(root)[2],13)
