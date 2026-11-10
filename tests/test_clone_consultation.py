import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tools.clone_app import Application


class ConsultationTests(unittest.TestCase):
    def test_mutation_and_sharing_are_refused_before_dialogs(self):
        app = object.__new__(Application)
        app.consultation_only = True
        app.forced_consultation = True
        app.status = Mock()
        app.edit_enabled = Mock()
        app.edit_enabled.get.return_value = True
        with patch('tools.clone_app.filedialog.askopenfilename') as dialog:
            self.assertFalse(app.can_edit())
            app.toggle_edit_mode()
            app.edit_mode_changed()
            app.add_at_center()
            app.import_notes()
            app.share_additions()
            app.restore_profile()
            app.append_route_point(1, 2)
            app.undo_route_point()
            app.finish_route()
            app.route_options()
            dialog.assert_not_called()
        self.assertIn(False, [call.args[0] for call in app.edit_enabled.set.call_args_list])
        self.assertIn('consultation', app.status.set.call_args.args[0])

    def test_original_code_persists_and_purge_relocks(self):
        with TemporaryDirectory() as directory:
            app = object.__new__(Application)
            app.consultation_only = True
            app.forced_consultation = False
            app.preferences_path = Path(directory) / 'client-preferences.json'
            app.preferences = {'consultation_only': True, 'database': 'US'}
            app.status = Mock()
            app.root = Mock()
            app.edit_enabled = Mock()
            app.edit_enabled.get.return_value = True
            app.save_preferences()
            with patch('tools.clone_app.simpledialog.askstring', return_value='bad'), patch('tools.clone_app.messagebox.showerror'):
                app.register_edit_code()
            self.assertTrue(app.consultation_only)
            with patch('tools.clone_app.simpledialog.askstring', return_value='6895'), patch('tools.clone_app.messagebox.showinfo'):
                app.register_edit_code()
            saved = json.loads(app.preferences_path.read_text(encoding='utf8'))
            self.assertEqual(saved['edit_authorization_codes'], ['6895'])
            self.assertEqual(saved['database'], 'US')
            self.assertFalse(saved['consultation_only'])
            self.assertFalse(app.consultation_only)
            with patch('tools.clone_app.messagebox.askyesno', return_value=True):
                app.purge_edit_codes()
            self.assertTrue(app.consultation_only)
            self.assertEqual(json.loads(app.preferences_path.read_text(encoding='utf8'))['edit_authorization_codes'], [])

    def test_code_requires_edit_mode_and_forced_consultation_blocks_it(self):
        app = object.__new__(Application)
        app.consultation_only = True
        app.forced_consultation = False
        app.edit_enabled = Mock()
        app.edit_enabled.get.return_value = False
        app.status = Mock()
        app.root = Mock()
        with patch('tools.clone_app.simpledialog.askstring') as prompt, patch('tools.clone_app.messagebox.showinfo'):
            app.register_edit_code()
            app.forced_consultation = True
            app.register_edit_code()
            prompt.assert_not_called()
