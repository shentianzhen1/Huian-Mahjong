import copy
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from workspace.vision.atlas_artwork_meld_probe import artwork_cells, load_candidates, probe


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


@unittest.skipUnless(importlib.util.find_spec('PIL') and importlib.util.find_spec('cv2'),
                     'Pillow and OpenCV required for symmetric probe')
class SymmetricNormalizationTests(unittest.TestCase):
    def test_query_artwork_and_real_references_share_transform(self):
        from PIL import Image
        from workspace.vision import public_meld_synthetic_transfer as transfer
        from workspace.vision.tiles_v0_1.labels import approved_labels as real_labels
        module = 'workspace.vision.atlas_artwork_meld_probe'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'templates').mkdir()
            image = Image.new('RGB', (24,40), 'white')
            image.save(root/'templates/p1.png')
            (root/'packet.zip').write_bytes(b'private packet placeholder')
            (root/'lineage.json').write_text('{}')
            queries = [{'image':image.copy(), 'match_group':'query', 'source_sha256':'a'*64,
                        'group_id':'g', 'tile_id':'P1', 'crop_sha256':'b'*64}]
            labels = [{'image':'templates/p1.png','tile_id':'P1','region':'hand_region',
                       'sha256':'c'*64,'bbox':[0,0,24,40]}]
            seen = []
            def transform(value):
                seen.append(value.size)
                return value.resize((56,96))
            def descriptors(value):
                self.assertEqual(value.size,(56,96))
                return None
            with patch(module+'.artwork_cells',return_value={'P1':image.copy()}), \
                 patch(module+'.load_candidates',return_value=(queries,{'prior_label_evidence_sha256':'d'*64})), \
                 patch(module+'.load_concealed_template_lineage',return_value={}), \
                 patch(module+'.verify_lineage_evidence_paths',return_value=[]), \
                 patch(module+'.qualify_concealed_template_labels',return_value=(labels,{})), \
                 patch('workspace.vision.tiles_v0_1.labels.approved_labels',return_value=labels), \
                 patch.object(transfer, '_canonical_face',side_effect=transform), \
                 patch.object(transfer, 'render_self_meld_variants',side_effect=lambda value:(value,)), \
                 patch('workspace.vision.public_meld_identity_sift._sift_descriptors',side_effect=descriptors):
                report=probe('sheet','e'*64,root/'packet.zip',root,root/'lineage.json',root,
                             normalization='canonical')
            self.assertEqual(seen,[(24,40)]*3)
            self.assertEqual(report['normalization_scope'],'query_and_all_references')
            self.assertFalse(report['safe_for_runtime'])
            self.assertEqual(report['rows'][0]['runtime_tile_id'],'UNKNOWN')
            self.assertIs(transfer.approved_labels, real_labels)
