from pathlib import Path
import unittest
from unittest.mock import patch

from workspace.hint_alpha.video_cli import launch_command, main


class VideoCliTests(unittest.TestCase):
    def test_gui_launch_uses_console_interpreter_and_keeps_space_paths_intact(self):
        command = launch_command('match clip.mp4', executable='runtime/pythonw.exe',
                                 output_root='evidence files', dataset_root='template files')
        self.assertEqual(command[0], 'runtime/python.exe')
        self.assertIn('match clip.mp4', command)
        self.assertIn('template files', command)
        self.assertEqual(command[-3:], ['--duration', '30', '--pause'])

    def test_cli_forwards_original_session_and_outputs_progress(self):
        def run(video, **options):
            self.assertEqual(video, Path('match.mp4'))
            self.assertEqual(options['source_session'], 'original-a')
            options['on_window']({'source_seconds': 1.0, 'timeline_event_count': 0,
                                 'runtime': {'display_allowed': False, 'hint': {'issues': ['hand_untrusted']}}})
            return {'report_path': 'report.json', 'timeline_text_path': 'report.txt'}
        with patch('workspace.hint_alpha.video_cli.run_video_test', side_effect=run), patch('builtins.print') as output:
            self.assertEqual(main(['match.mp4', '--output', 'report.json', '--source-session', 'original-a']), 0)
        self.assertTrue(any('UNKNOWN' in str(call) for call in output.call_args_list))

    def test_cli_error_has_nonzero_exit(self):
        with patch('workspace.hint_alpha.video_cli.run_video_test', side_effect=ValueError('bad video')), patch('builtins.print'):
            self.assertEqual(main(['match.mp4', '--output', 'report.json']), 1)
