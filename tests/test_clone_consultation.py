import unittest
from unittest.mock import Mock, patch

from tools.clone_app import Application


class ConsultationTests(unittest.TestCase):
    def test_mutation_and_sharing_are_refused_before_dialogs(self):
        app = object.__new__(Application)
        app.consultation_only = True
        app.status = Mock()
        app.edit_enabled = Mock()
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
        app.edit_enabled.set.assert_called_once_with(False)
        self.assertIn('consultation', app.status.set.call_args.args[0])
