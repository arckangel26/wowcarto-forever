"""State preservation regressions against real Tk widgets and local reference data."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from PIL import ImageTk

from tools.clone_app import Application
from tools.clone_annotation_dialog import AnnotationDialog


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('WCF_CLIENT_DATA', ROOT / 'outputs/clone-windows-legacy-v2-20261106/WoWCartoForever-Client/data'))


@unittest.skipUnless((DATA / 'catalog.json').is_file(), 'Local proprietary reference data not supplied')
class InterfacesTests(unittest.TestCase):
    def test_native_map_glyphs_and_player_level_persist(self):
        app = self.app
        self.assertEqual((app.map.icons[7].width(), app.map.icons[7].height()), (22, 22))
        self.assertEqual((app.region_tree_icon.width(), app.region_tree_icon.height()), (16, 16))
        for category, expected in ((7, (10, 10)), (6, (14, 14)), (32, (22, 22))):
            bounds = ImageTk.getimage(app.map.icons[category]).getbbox()
            self.assertEqual((bounds[2] - bounds[0], bounds[3] - bounds[1]), expected)
        self.assertEqual(app.model.categories[7]['map_icon_index'], 0)
        self.assertEqual(app.model.categories[6]['map_icon_index'], 1)
        self.assertEqual(app.model.categories[32]['map_icon_index'], 28)
        app.level.set('60'); self.assertEqual(app.map.player_level, 60)
        app.level.set(''); app.update_player_level(normalize=True)
        self.assertEqual(app.level.get(), '60')
        app.level.set('99'); app.update_player_level(normalize=True)
        self.assertEqual(app.level.get(), '85')
        app.level.set('20'); self.close()
        self.app = Application(DATA, self.path, offline=True)
        self.assertEqual(self.app.map.player_level, 20)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'annotations.sqlite3'
        self.app = Application(DATA, self.path, offline=True)
        self.app.root.update(); self.app.initial_view()
        self.addCleanup(self.close)

    def close(self):
        if self.app is not None:
            self.app.root.update_idletasks()
            self.app.close(); self.app = None

    def test_interface_switch_preserves_data_view_query_filters_selection_and_search_window(self):
        app = self.app
        iid = next(iid for iid in app.groups if 'Azshara' in app.regions.item(iid, 'text'))
        app.select_region_marker(iid)
        row = next(row for row in app.map.records if row['category'] != 18)
        app.map.selected = row['key']; app.select_record(row)
        app.map.zoom_to(.7); app.map.move(35, 20)
        app.query.set('Azshara'); app.search_options = {'categories': {7}, 'comment': True}
        app.map.category_filter = {7, 37}
        app.show_search(); app.root.update()
        search = next(w for w in app.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Recherche')
        canvas, model = app.map, app.model
        before = (app.mode.get(), app.shown_region, app.map.cx, app.map.cy, app.map.scale,
                  app.map.selected, app.selection, app.map.records, app.search_options, app.query.get())
        for interface in ('Modern', 'Legacy'):
            app.set_interface(interface); app.root.update()
            after = (app.mode.get(), app.shown_region, app.map.cx, app.map.cy, app.map.scale,
                     app.map.selected, app.selection, app.map.records, app.search_options, app.query.get())
            self.assertEqual(after, before)
            self.assertIs(app.map, canvas); self.assertIs(app.model, model)
            self.assertTrue(search.winfo_exists()); self.assertEqual(app.map.category_filter, {7, 37})
        search.destroy()

    def test_switch_preserves_actual_unsaved_annotation_dialog(self):
        app = self.app
        observations = []
        def switch():
            editor = next(w for w in app.root.winfo_children() if isinstance(w, AnnotationDialog))
            editor.name.set('Brouillon à conserver')
            editor.comment.insert('1.0', 'Texte non enregistré')
            for interface in ('Modern', 'Legacy'):
                app.set_interface(interface); app.root.update_idletasks()
                observations.append((editor.name.get(), editor.comment.get('1.0', 'end-1c'), editor.winfo_exists()))
            editor.cancel()
        app.root.after(100, switch)
        result = AnnotationDialog(app.root, dict(name='', map_id=17, x=100, y=200), app.model.categories, app.tr).result
        self.assertIsNone(result)
        self.assertEqual(observations, [('Brouillon à conserver', 'Texte non enregistré', 1)] * 2)
        self.assertEqual(app.store.notes(), [])

    def test_restart_preserves_profile_navigation_and_categories_without_network(self):
        app = self.app
        iid = next(iid for iid in app.groups if app.regions.item(iid, 'text') == 'Féralas')
        app.select_region_marker(iid); app.map.zoom_to(.8); app.map.move(10, 20)
        app.map.category_filter = {7, 37}; app.set_interface('Modern')
        app.query.set('Brouillon'); app.search_options = {'categories': {37}}
        app.store.add_note(dict(name='Persistante', map_id=17, x=120, y=200,
                               source_ref=app.model.personal_prefix + 'test'))
        before = app.map.cx, app.map.cy, app.map.scale, app.region_native_ids[app.shown_region]
        self.close()
        self.app = Application(DATA, self.path, offline=True)
        self.app.root.update(); self.app.initial_view()
        other = self.app
        self.assertEqual(other.interface.get(), 'Modern')
        self.assertEqual((other.map.cx, other.map.cy, other.map.scale, other.region_native_ids[other.shown_region]), before)
        self.assertEqual(other.map.category_filter, {7, 37})
        self.assertEqual(other.store.notes()[0]['name'], 'Persistante')
        self.assertEqual(other.query.get(), 'Brouillon')
        other.sync(); self.assertIn('hors ligne', other.status.get())

    def test_restart_from_cross_continent_search_rebuilds_correct_region_markers(self):
        app = self.app
        row = next(row for row in app.model.by_group[0] if row['category'] != 18)
        iid = app.results_tree.insert('', 'end', text=row['name'])
        app.results = {iid: row}; app.results_tree.selection_set(iid); app.select_result()
        app.root.update()
        self.assertEqual(app.group, 0); self.assertIsNone(app.shown_region)
        selected = app.map.selected
        self.close()
        self.app = Application(DATA, self.path, offline=True)
        self.app.root.update(); self.app.initial_view()
        other = self.app
        self.assertEqual(other.group, 0); self.assertEqual(other.map.selected, selected)
        self.assertEqual(other.regions.selection(), ())
        expected = {iid for iid in other.region_centers if other.groups[iid][0] == 0}
        self.assertEqual({row['iid'] for row in other.map.region_markers}, expected)

    def test_restored_preferences_survive_close_and_apply_at_next_start(self):
        from tools.clone_profile import backup_profile
        backup = Path(self.directory.name) / 'restored.wcfbackup'
        backup_profile(self.app.store, {'interface': 'Modern', 'map_mode': 'Legacy', 'theme': 'dark'}, backup)
        with patch('tools.clone_app.filedialog.askopenfilename', return_value=str(backup)), patch('tools.clone_app.messagebox.showinfo'):
            self.app.restore_profile()
        self.assertEqual(self.app.interface.get(), 'Legacy')
        self.close()
        self.app = Application(DATA, self.path, offline=True)
        self.app.root.update(); self.app.initial_view()
        self.assertEqual(self.app.interface.get(), 'Modern')
        self.assertEqual(self.app.mode.get(), 'Legacy')
        self.assertTrue(self.app.dark_theme.get())


if __name__ == '__main__': unittest.main()
