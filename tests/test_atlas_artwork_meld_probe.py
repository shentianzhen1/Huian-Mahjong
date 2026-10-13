import copy
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from workspace.vision.atlas_artwork_meld_probe import artwork_cells, load_candidates


@unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow required for packet image contracts')
class UploadedArtworkPacketTests(unittest.TestCase):
    def test_sheet_geometry_hash_and_caption_exclusion(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sheet.png'
            image=Image.new('RGB',(900,720),'white')
            image.paste('black',(0,110,100,130))
            image.save(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            cells=artwork_cells(path,digest)
            self.assertEqual(len(cells),42)
            self.assertEqual(cells['P1'].size,(100,108))
            self.assertEqual(cells['P1'].getpixel((50,107)),(255,255,255))
            with self.assertRaises(ValueError): artwork_cells(path,'0'*64)
            Image.new('RGB',(900,719),'white').save(path)
            with self.assertRaises(ValueError): artwork_cells(path,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_packet_checks_prior_labels_file_bytes_and_decoded_pixels(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            image=Image.new('RGB',(8,12),'red')
            buffer=BytesIO(); image.save(buffer,format='PNG'); raw=buffer.getvalue()
            sha=lambda data: hashlib.sha256(data).hexdigest()
            old={'recovery_id':'g','status':'PRIVATE_TEMPLATE_EVIDENCE_RECOVERED',
                 'source_sha256':'a'*64,'match_group':'match','frame_index':1,
                 'faces':[{'tile_id':'M1','bbox':[0,0,8,12],'crop_sha256':'f'*64}]}
            prior=root/'review.json';prior.write_text(json.dumps({'items':[old]}))
            manifest={'schema_version':'huian_redecoded_meld_candidates_v0_1','development_only':True,
                'legacy_approved_packet_reconstructed':False,'formal_promotion_evidence':False,
                'safe_for_runtime':False,'safe_for_hint':False,'safe_for_executor':False,
                'prior_label_evidence_path':'review.json','prior_label_evidence_sha256':sha(prior.read_bytes()),
                'groups':[{'group_id':'g','source_sha256':'a'*64,'match_group':'match','decoded_frame_index':1,
                    'faces':[{'tile_id_from_existing_human_label':'M1','bbox':[0,0,8,12],
                        'legacy_crop_sha256':'f'*64,'crop_file':'candidate_faces/a.png',
                        'crop_file_sha256':sha(raw),'raw_rgb_sha256':sha(image.tobytes()),'size':[8,12],
                        'runtime_admission':False}]}]}
            packet=root/'packet.zip'
            def write(value):
                with zipfile.ZipFile(packet,'w') as archive:
                    archive.writestr('candidate_manifest.json',json.dumps(value))
                    archive.writestr('candidate_faces/a.png',raw)
            write(manifest)
            faces,_=load_candidates(packet,root)
            self.assertEqual(faces[0]['tile_id'],'M1')
            for field,value in [('crop_file_sha256','0'*64),('raw_rgb_sha256','0'*64),
                                ('tile_id_from_existing_human_label','M2'),('runtime_admission',True)]:
                altered=copy.deepcopy(manifest);altered['groups'][0]['faces'][0][field]=value
                write(altered)
                with self.subTest(field=field), self.assertRaises(ValueError): load_candidates(packet,root)
            altered=copy.deepcopy(manifest);altered['groups'].append(copy.deepcopy(altered['groups'][0]))
            write(altered)
            with self.assertRaises(ValueError): load_candidates(packet,root)
