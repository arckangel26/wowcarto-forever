"""Search criteria survive filtering, history recall and region-scoped execution."""
import json
import struct
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.clone_model import Model, folded
from tools.clone_search_dialog import SearchDialog, value_key


def region(ident, name, left=0):
    coordinates = struct.pack('>ii', left * 256, 0)
    coordinates += b''.join(struct.pack('>hh', *delta) for delta in ((25600, 0), (0, -25600), (-25600, 0)))
    return dict(id=ident, name=name, group_id=0, links='S_' + coordinates.hex(), wx=left + 50, wy=50)


class SearchDialogTests(unittest.TestCase):
    def setUp(self):
        try: self.root = tk.Tk()
        except tk.TclError as error: self.skipTest(str(error))
        self.root.withdraw(); self.addCleanup(self.root.destroy)
        model = object.__new__(Model)
        model.categories = {7: dict(name='Mob'), 6: dict(name='Unique')}
        model.db = dict(flags={16: dict(name='Élite', parent=0), 54: dict(name='Rare', parent=0)},
                        continents=[dict(id=0, name='Azeroth')])
        model.index = None; model.groups = {0: dict(continent_id=0)}
        records = [dict(key='normal', category=7, group_id=0, source='native', min_level=10, max_level=12,
                        name='Loup', comment='Bois', property_names=[], wx=50, wy=50),
                   dict(key='elite', category=6, group_id=0, source='personal', min_level=11, max_level=11,
                        name='Loup rare', comment='Bois', property_names=['Élite'], wx=50, wy=50)]
        model.annotations = [dict(row, search_name=folded(row['name'])) for row in records]
        model.geographic_regions = lambda: [region(9, 'Bois'), region(10, 'Prairie', 200)]
        self.app = SimpleNamespace(root=self.root, model=model, query=tk.StringVar(self.root),
                                   mode=tk.StringVar(self.root, 'Référence 1.20'),
                                   database=tk.StringVar(self.root, 'Francais'), preferences={}, search_options={},
                                   search_history=[], category_icons={}, toolbar_icons={},
                                   region_native_ids={'selected': 9}, shown_region='selected', tr=lambda text: text)
        self.calls = []
        self.app.search = lambda: self.calls.append(model.search(self.app.query.get(), **self.app.search_options))

    def dialog(self, **kwargs):
        dialog = SearchDialog(self.app, **kwargs)
        self.root.update_idletasks()
        return dialog

    def test_filtering_does_not_erase_checked_category_or_property(self):
        dialog = self.dialog()
        dialog.toggle('category:6'); dialog.toggle('property:16')
        dialog.filter_text.set('Prairie')
        self.assertFalse(dialog.tree.exists('category:6'))
        options = dialog.current_options()
        self.assertEqual(options['categories'], [6]); self.assertEqual(options['properties'], ['Élite'])
        dialog.filter_text.set('')
        self.assertTrue(dialog.tree.item('category:6', 'text').startswith('☑'))
        dialog.toggle(dialog.roots['categories'])
        self.assertEqual(dialog.current_options()['categories'], [6])
        self.app.query.set('Loup'); self.assertTrue(dialog.run())
        self.assertEqual([row['key'] for row in self.calls[0]], ['elite'])

    def test_history_restores_query_and_every_option_from_json(self):
        self.app.query.set('Loup')
        options = dict(name=False, comment=True, categories={6}, properties=['Élite'], continents={0},
                       regions=[[0, [[0, 0], [100, 0], [100, 100], [0, 100]]]],
                       minimum=11, maximum=12, local_only=True)
        self.app.search_options = options
        dialog = self.dialog(); self.assertTrue(dialog.run())
        # Preferences must round-trip through an actual JSON document.
        self.app.preferences = json.loads(json.dumps(self.app.preferences))
        self.app.query.set('Autre'); self.app.search_options = {}
        dialog = self.dialog(); dialog.recall(0)
        self.assertEqual(self.app.query.get(), 'Loup')
        self.assertEqual(value_key(dialog.current_options()), value_key(options))
        self.assertEqual(dialog.summary.cget('state'), 'disabled')

    def test_new_search_resets_fields_without_destroying_previous_preset(self):
        self.app.query.set('Loup'); self.app.search_options = {'categories': {7}, 'comment': True}
        dialog = self.dialog(clear=True)
        self.assertEqual(self.app.query.get(), '')
        self.assertIsNone(dialog.current_options()['categories'])
        self.assertEqual(self.app.preferences['search_presets'][0]['query'], 'Loup')
        dialog.recall(0)
        self.assertEqual(dialog.current_options()['categories'], [7])
        self.assertTrue(dialog.comments.get())

    def test_invalid_range_and_missing_current_region_do_not_execute_broad_search(self):
        dialog = self.dialog(current=True)
        self.app.query.set('Loup'); self.app.shown_region = None
        with patch('tools.clone_search_dialog.messagebox.showerror') as error:
            self.assertFalse(dialog.run()); error.assert_called_once()
        self.assertEqual(self.calls, [])
        self.app.shown_region = 'selected'
        dialog.use_level.set(True); dialog.minimum.set('20'); dialog.maximum.set('10')
        with patch('tools.clone_search_dialog.messagebox.showerror'):
            self.assertFalse(dialog.run())
        self.assertEqual(self.calls, [])
        dialog.minimum.set('10'); dialog.maximum.set('12'); self.assertTrue(dialog.run())
        self.assertEqual(len(self.calls[0]), 2)

    def test_space_toggles_checkbox_and_summary_tracks_live_query(self):
        dialog = self.dialog(); dialog.tree.focus('category:7'); dialog._space(None)
        self.app.query.set('Loup')
        self.assertIn('Loup', dialog.summary.get('1.0', 'end'))
        self.assertIn('Mob', dialog.summary.get('1.0', 'end'))
        self.assertEqual(dialog.current_options()['categories'], [7])
        self.root.deiconify(); dialog.deiconify(); self.root.update()
        dialog.set_expanded(True); self.root.update()
        self.assertTrue(dialog.expanded); self.assertTrue(dialog.geometry().startswith('540x629'))
        dialog.set_expanded(False); self.root.update()
        self.assertTrue(dialog.geometry().startswith('540x350'))

    def test_empty_explicit_filter_and_legacy_history_are_preserved(self):
        self.app.search_options = {'categories': []}
        self.app.search_history = ['Ancienne recherche']
        dialog = self.dialog()
        self.assertEqual(dialog.current_options()['categories'], [])
        self.assertEqual(dialog.visible_presets[0]['query'], 'Ancienne recherche')
        dialog.recall(0); self.assertEqual(self.app.query.get(), 'Ancienne recherche')
        self.assertIsNone(dialog.current_options()['categories'])

    def test_group_roots_and_empty_property_lists_cannot_trigger_unfiltered_search(self):
        self.app.search_options = {'properties': [], 'regions': []}
        dialog = self.dialog(); dialog.toggle(dialog.roots['properties'])
        with patch('tools.clone_search_dialog.messagebox.showerror'):
            self.assertFalse(dialog.run())
        self.assertEqual(self.calls, [])


if __name__ == '__main__': unittest.main()
