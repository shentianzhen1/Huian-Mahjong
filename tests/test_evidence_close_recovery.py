import tempfile
import unittest
from unittest.mock import patch
from workspace.hint_alpha.evidence import EvidenceSession


class EvidenceCloseRecoveryTests(unittest.TestCase):
    def test_failed_completion_write_remains_retryable(self):
        with tempfile.TemporaryDirectory() as root:
            session = EvidenceSession(root)
            with patch('workspace.hint_alpha.evidence._write_json', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    session.close()
            session.mark('CLOSE_RETRY')
            result = session.close('retry')
            self.assertEqual(result['reason'], 'retry')
            self.assertTrue((session.path / 'completion.json').exists())
