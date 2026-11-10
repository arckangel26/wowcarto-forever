import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from tools.clone_annotation_dialog import AnnotationDialog, local_fields
from tools.clone_store import Store, ConflictError


class AnnotationEditorTests(unittest.TestCase):
    def editor(self, initial, *, editable_tags=True):
        root = tk.Tk(); root.withdraw(); self.addCleanup(root.destroy)
        def nonmodal(dialog, parent, title=None):
            tk.Toplevel.__init__(dialog, parent); dialog.withdraw()
            dialog.parent = parent; dialog.result = None
            body = tk.Frame(dialog); body.pack(fill='both', expand=True)
            dialog.body(body); dialog.buttonbox()
        categories = {7: dict(name='Pnj Commun (Mob)', native_class=1, color_rgb='#eff0de'),
                      37: dict(name='Note', native_class=0, color_rgb='#ffffff')}
        properties = {57: dict(name='Type', parent=0), 58: dict(name='Bête', parent=57),
                      16: dict(name='Élite', parent=0)}
        with patch('tools.clone_annotation_dialog.simpledialog.Dialog.__init__', nonmodal):
            dialog = AnnotationDialog(root, initial, categories, lambda text: text,
                                      editable_tags=editable_tags, properties=properties, player_level=20)
        root.update_idletasks()
        return root, dialog

    def test_native_three_column_form_edits_properties_without_losing_unknown_metadata(self):
        raw = dict(name='Créature', map_id=17, x=123, y=456, category=7, min_level=25, max_level=25,
                   comment='[commande native]\nTexte brut\n', tags='Tag personnel; Bête', flags='opaque-source')
        root, dialog = self.editor(raw)
        self.assertEqual(len(dialog.pages.tabs()), 2)
        self.assertEqual(len(dialog.comment_pages.tabs()), 3)
        self.assertEqual(dialog.property_tree.parent('58'), '57')
        self.assertEqual(dialog.preview.cget('background'), '#f82515')
        dialog.property_tree.selection_set('16'); dialog.toggle_property()
        self.assertEqual(dialog.tags.get(), 'Tag personnel; Bête; Élite')
        dialog.name.set('Autre créature')
        self.assertTrue(dialog.validate()); dialog.apply()
        self.assertEqual(dialog.result['flags'], 'opaque-source')
        self.assertEqual((dialog.result['map_id'], dialog.result['x'], dialog.result['y']), (17, 123, 456))
        self.assertEqual(dialog.result['comment'], raw['comment'])
        self.assertEqual(raw['name'], 'Créature')

    def test_advanced_comment_and_common_level_helper_update_general_fields(self):
        root, dialog = self.editor(dict(name='Note', map_id=1, x=2, y=3, category=37, comment='Avant'))
        dialog.pages.select(dialog.advanced_page)
        dialog.advanced_comment.delete('1.0', 'end')
        dialog.advanced_comment.insert('1.0', '[Loc_Ref=123]\nÉcrit dans la vue avancée\n\n')
        dialog.wizard_level.set('36'); dialog.apply_common_level()
        self.assertEqual((dialog.minimum.get(), dialog.maximum.get()), ('36', '36'))
        self.assertTrue(dialog.validate()); dialog.apply()
        self.assertEqual(dialog.result['comment'], '[Loc_Ref=123]\nÉcrit dans la vue avancée\n\n')
        self.assertEqual((dialog.result['min_level'], dialog.result['max_level']), (36, 36))

    def test_read_only_properties_and_invalid_range_preserve_source(self):
        root, dialog = self.editor(dict(name='Note', map_id=1, x=2, y=3, category=37, tags='Original'),
                                   editable_tags=False)
        dialog.property_tree.selection_set('16'); dialog.toggle_property()
        self.assertEqual(dialog.tags.get(), 'Original')
        dialog.tags.set('Modification extérieure')
        self.assertTrue(dialog.validate()); dialog.apply()
        self.assertEqual(dialog.result['tags'], 'Original')
        dialog.minimum.set('30'); dialog.maximum.set('10')
        with patch('tools.clone_annotation_dialog.messagebox.showerror') as error:
            self.assertFalse(dialog.validate())
        error.assert_called_once()

    def test_native_metadata_and_coordinates_survive_local_override(self):
        native=dict(name='Point',comment='Description',category=7,map_id=17,x=123,y=456,
                    min_level=10,max_level=20,property_names=['Herbe','Rare'],flags=(1,2,3))
        fields=local_fields(native)
        self.assertEqual((fields['map_id'],fields['x'],fields['y']),(17,123,456))
        self.assertEqual(fields['tags'],'Herbe; Rare')
        self.assertEqual(json.loads(fields['flags']),[1,2,3])
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'notes.sqlite3') as store:
            note=store.set_override('native:reference120:Francais:1',fields)
            changed=dict(fields,name='Correction',comment='Autre description',min_level=11)
            store.update_note(note['id'],changed,expected_revision=note['revision'])
            with self.assertRaises(ConflictError):
                store.update_note(note['id'],{'comment':'Ancienne version'},expected_revision=note['revision'])
            saved=store.get_note(note['id'])
            self.assertEqual((saved['name'],saved['comment'],saved['x'],saved['y']),('Correction','Autre description',123,456))
            self.assertEqual(len(store.history(note['id'])),2)
            self.assertEqual(native['name'],'Point')

    def test_existing_note_flags_are_not_reencoded(self):
        row=dict(name='Local',map_id=1,x=2,y=3,tags='A; B',flags='{"opaque":1}')
        fields=local_fields(row)
        self.assertEqual(fields['flags'],'{"opaque":1}')
        self.assertEqual(fields['tags'],'A; B')

    def test_hiding_is_revision_checked_and_reversible(self):
        from tools.clone_app import Application
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'notes.sqlite3') as store:
            note_id=store.add_note(dict(name='Local',map_id=1,x=2,y=3,source_ref='personal:reference120:Francais:test'))
            app=Application.__new__(Application); app.can_edit=lambda:True; app.store=store
            app.tr=lambda text:text; app.root=Mock(); app.status=Mock(); app.refresh_local_annotations=Mock()
            with patch('tools.clone_app.messagebox.askyesno',return_value=True):
                app.hide_local_note({'note_id':note_id,'revision':1})
            self.assertTrue(store.get_note(note_id)['deleted'])
            self.assertEqual(store.get_note(note_id)['revision'],2)
            store.restore_note(note_id,expected_revision=2)
            self.assertFalse(store.get_note(note_id)['deleted'])
            self.assertEqual(len(store.history(note_id)),3)

if __name__=='__main__': unittest.main()
