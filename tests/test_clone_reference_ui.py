"""Behavioral integration checks for the public 1.20-style client interface."""
import hashlib
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('WCF_CLIENT_DATA', ROOT / 'outputs/clone-windows-legacy-v2-20261106/WoWCartoForever-Client/data'))


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def text_contents(widget):
    return '\n'.join(child.get('1.0', 'end-1c') for child in descendants(widget) if isinstance(child, tk.Text))


@unittest.skipUnless((DATA / 'catalog.json').is_file(), 'Local proprietary reference data not supplied')
class ReferenceInterfaceTests(unittest.TestCase):
    def setUp(self):
        from tools.clone_app import Application
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'annotations.sqlite3'
        # Any unexpected modal error is a failed test, rather than a blocked run.
        errors = patch('tkinter.messagebox.showerror', side_effect=AssertionError('Unexpected error dialog'))
        info = patch('tkinter.messagebox.showinfo')
        errors.start(); info.start(); self.addCleanup(errors.stop); self.addCleanup(info.stop)
        self.app = Application(DATA, self.path, offline=True)
        self.callback_errors = []
        self.app.root.report_callback_exception = lambda kind, value, trace: self.callback_errors.append(value)
        self.addCleanup(self.assertEqual, self.callback_errors, [])
        self.addCleanup(self.close)
        self.pump(); self.app.initial_view(); self.pump()

    def pump(self):
        self.app.root.update()
        self.assertEqual(self.callback_errors, [])

    def close(self):
        if self.app is not None:
            self.app.root.update_idletasks()
            self.app.close(); self.app = None

    def native_row(self):
        return next(row for row in self.app.model.annotations
                    if row['source'] == 'native' and row['category'] == 7
                    and self.app.model.tiles[row['map_id']].get('standard'))

    def test_function_keys_switch_real_docked_panes(self):
        app = self.app
        panels = {'regions': app.region_pane, 'master': app.master_pane,
                  'results': app.results_pane, 'details': app.detail_window}
        self.assertIsInstance(app.result_window, tk.Frame)
        self.assertIsInstance(app.detail_window, tk.Frame)
        for key, name in (('F1', 'regions'), ('F2', 'master'), ('F3', 'results'), ('F4', 'details')):
            with self.subTest(key=key):
                app.root.focus_force(); app.root.event_generate('<' + key + '>'); self.pump()
                self.assertEqual(app.active_pane, name)
                self.assertEqual(panels[name].winfo_manager(), 'pack')
                self.assertIs(panels[name].master, app.panes)
                self.assertTrue(all(not panel.winfo_manager() for other, panel in panels.items() if other != name))
        self.assertIn(app.database.get(), app.database_info.cget('text'))
        self.assertFalse(any(isinstance(child, tk.Toplevel) and child.title() in
                             ('Résultats des annotations', 'Détails de l’annotation')
                             for child in app.root.winfo_children()))

    def test_master_expansion_batches_without_losing_records_and_centers_selection(self):
        app = self.app
        count = len(app.model.annotations)
        app.show_pane('master'); self.pump()
        self.assertGreater(len(app.master_nodes), 0)
        self.assertEqual(app.master_records, {})
        category = max(app.master_nodes, key=lambda node: len(app.master_nodes[node]))
        records = app.master_nodes[category]
        self.assertGreater(len(records), 1000)
        app.master_tree.focus(category); app.expand_master(); self.pump()
        self.assertEqual(len(app.master_records), 500)
        first_keys = {row['key'] for row in app.master_records.values()}
        more = next(iid for iid in app.master_more if app.master_more[iid][0] == category)
        app.master_tree.selection_set(more); app.select_master(); self.pump()
        self.assertEqual(len(app.master_records), 1000)
        self.assertTrue(first_keys < {row['key'] for row in app.master_records.values()})
        chosen, row = next((iid, row) for iid, row in app.master_records.items() if row['key'] == records[999]['key'])
        app.master_tree.selection_set(chosen); app.select_master(); self.pump()
        self.assertEqual(app.map.selected, row['key'])
        self.assertEqual(app.selection['key'], row['key'])
        self.assertEqual((app.map.cx, app.map.cy), (row['wx'], row['wy']))
        self.assertEqual(app.group, row['group_id'])
        self.assertEqual(len(app.model.annotations), count)

    def test_help_toolbar_action_opens_shortcuts_instead_of_about(self):
        app = self.app
        help_button = next(button for button in app.legacy_bar.winfo_children()
                           if isinstance(button, tk.Button) and button.cget('image') == str(app.toolbar_icons[22]))
        help_button.invoke(); self.pump()
        self.assertIn('raccourcis', app.help_window.title())
        contents = text_contents(app.help_window)
        self.assertIn('Ctrl+F', contents); self.assertIn('F1 / F2 / F3 / F4', contents)
        self.assertIn('Ctrl+C', contents)
        self.assertFalse(getattr(app, 'about_window', None))
        about_button = next(button for button in app.legacy_bar.winfo_children()
                            if isinstance(button, tk.Button) and button.cget('image') == str(app.toolbar_icons[7]))
        about_button.invoke(); self.pump()
        self.assertIn('À propos', app.about_window.title())
        self.assertIn('0.9.1', text_contents(app.about_window))
        self.assertGreater(app.help_window.winfo_width(), app.about_window.winfo_width())

    def test_text_editing_does_not_trigger_single_letter_map_shortcuts(self):
        app = self.app
        entry = app.filter_entry
        initial = app.map.dim
        entry.insert(0, 's')
        text_event = SimpleNamespace(widget=entry, keysym='s', state=0)
        self.assertIsNone(app.reference_key(text_event, app.toggle_dim))
        self.assertEqual(app.map.dim, initial)
        self.assertEqual(entry.get(), 's')
        map_event = SimpleNamespace(widget=app.map, keysym='s', state=0)
        self.assertEqual(app.reference_key(map_event, app.toggle_dim), 'break')
        self.assertEqual(app.map.dim, not initial)
        self.assertTrue(app.root.bind('s'))

    def test_new_search_clears_parameters_and_previous_search_keeps_them(self):
        app = self.app
        app.query.set('Féralas'); app.search_options = {'categories': {7}, 'minimum': 10, 'maximum': 20}
        app.root.focus_force(); app.root.event_generate('<Control-f>'); self.pump()
        self.assertEqual(app.query.get(), '')
        self.assertEqual(app.search_options, {})
        windows = [child for child in app.root.winfo_children() if isinstance(child, tk.Toplevel) and child.title() == 'Recherche']
        self.assertEqual(len(windows), 1)
        windows[0].destroy(); self.pump()
        app.query.set('Créature'); previous = {'categories': {7}, 'comment': True}
        app.search_options = previous.copy()
        app.root.focus_force(); app.root.event_generate('<Control-g>'); self.pump()
        self.assertEqual(app.query.get(), 'Créature')
        self.assertEqual(app.search_options, previous)
        self.assertTrue(any(isinstance(child, tk.Toplevel) and child.title() == 'Recherche'
                            for child in app.root.winfo_children()))

    def test_copy_paste_and_cut_keep_native_source_and_restorable_history(self):
        app = self.app
        # Exercise the application serialization and real SQLite persistence
        # without replacing arbitrary user clipboard formats (including images).
        clipboard = ['']
        for name, callback in (
                ('clipboard_clear', lambda: clipboard.__setitem__(0, '')),
                ('clipboard_append', lambda value: clipboard.__setitem__(0, clipboard[0] + value)),
                ('clipboard_get', lambda: clipboard[0])):
            replacement = patch.object(app.root, name, side_effect=callback)
            replacement.start(); self.addCleanup(replacement.stop)
        app.edit_enabled.set(True); app.edit_database.set(app.database.get())
        row = self.native_row(); original = deepcopy(row)
        source = DATA / app.model.map_set['databases'][app.database.get()]['path']
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        app.selection = row; app.copy_annotation()
        copied = json.loads(app.root.clipboard_get())
        self.assertEqual(copied['data']['name'], row['name'])
        tile = app.model.tiles[row['map_id']]
        app.paste_annotation((tile, tile['x'] + 100, tile['y'] + 80)); self.pump()
        pasted = app.store.notes()[0]
        self.assertEqual((pasted['map_id'], pasted['x'], pasted['y']), (tile['id'], 25600, 20480))
        self.assertEqual(pasted['name'], row['name'])
        self.assertIn(row['key'], app.model.by_key)
        app.selection = app.model.by_key[row['key']]; app.copy_annotation(cut=True); self.pump()
        tombstone = next(note for note in app.store.notes(include_deleted=True) if note['source_ref'] == row['key'])
        self.assertTrue(tombstone['deleted'])
        self.assertNotIn(row['key'], app.model.by_key)
        app.store.restore_note(tombstone['id'], expected_revision=tombstone['revision'])
        app.refresh_local_annotations(); self.pump()
        self.assertEqual(app.model.by_key['note:' + tombstone['id']]['name'], original['name'])
        self.assertEqual(len(app.store.history(tombstone['id'])), 2)
        pasted_row = app.model.by_key['note:' + pasted['id']]
        app.selection = pasted_row; app.copy_annotation(cut=True); self.pump()
        self.assertTrue(app.store.get_note(pasted['id'])['deleted'])
        self.assertEqual(len(app.store.history(pasted['id'])), 2)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        self.assertEqual(row, original)

    def test_paths_switch_renders_a_real_native_vector_and_hides_it_again(self):
        app = self.app
        candidates = ((row, app.native_path(row)) for row in app.model.annotations if row.get('links', '').startswith('V_'))
        row, path = next((row, path) for row, path in candidates if path is not None and len(path.points) >= 2)
        app.focus_record(row)
        xs, ys = zip(*path.points)
        app.map.fit_bounds((min(xs), min(ys), max(xs), max(ys)))
        app.map.annotations_visible = True; app.map.paths_visible = False
        app.map.draw(); self.assertEqual(app.map.find_withtag('native-paths'), ())
        app.toggle_paths(); app.map.draw()
        self.assertTrue(app.map.find_withtag('native-paths'))
        app.toggle_paths(); app.map.draw()
        self.assertEqual(app.map.find_withtag('native-paths'), ())
        self.assertEqual(app.native_path(row), path)

    def test_display_options_mode_and_notes_survive_restart(self):
        from tools.clone_app import Application
        app = self.app
        row = self.native_row(); app.focus_record(row)
        app.set_interface('Modern')
        app.map.paths_visible = True; app.map.annotations_visible = False
        note_id = app.store.add_note(dict(name='Note conservée', map_id=row['map_id'], x=100, y=200,
                                          source_ref=app.model.personal_prefix + 'reference-ui-test'))
        before = app.map.cx, app.map.cy, app.map.scale
        self.close()
        self.app = Application(DATA, self.path, offline=True)
        self.app.root.report_callback_exception = lambda kind, value, trace: self.callback_errors.append(value)
        self.pump(); self.app.initial_view(); self.pump()
        self.assertEqual(self.app.version, '0.9.1')
        self.assertEqual(self.app.interface.get(), 'Modern')
        self.assertEqual(self.app.mode.get(), 'Référence 1.20')
        self.assertTrue(self.app.map.paths_visible); self.assertFalse(self.app.map.annotations_visible)
        self.assertEqual((self.app.map.cx, self.app.map.cy, self.app.map.scale), before)
        self.assertEqual(self.app.store.get_note(note_id)['name'], 'Note conservée')

    def test_welcome_is_explicit_and_commencer_saves_first_run_preferences(self):
        app = self.app
        self.assertFalse(getattr(app, 'welcome_window', None))
        self.assertFalse(app.preferences.get('welcome_seen', False))
        app.show_welcome(); self.pump()
        self.assertIn('Bienvenue', app.welcome_window.title())
        start = next(child for child in descendants(app.welcome_window)
                     if isinstance(child, tk.Button) and child.cget('text') == 'Commencer')
        start.invoke(); self.pump()
        saved = json.loads(app.preferences_path.read_text(encoding='utf-8'))
        self.assertTrue(saved['welcome_seen']); self.assertTrue(saved['data_notice_seen'])
        self.assertFalse(app.welcome_window.winfo_exists())
        self.assertEqual(app.store.notes(), [])

    def test_alt_f4_does_not_activate_information_panel(self):
        app = self.app; app.root.focus_force(); self.pump()
        with patch.object(app, 'close') as close:
            app.root.event_generate('<Alt-F4>'); self.pump()
            close.assert_called_once()
        self.assertEqual(app.active_pane, 'regions')

    def test_local_edit_keeps_native_vector_geometry_and_source_file(self):
        from tools.clone_annotation_dialog import local_fields
        app = self.app
        row = next(row for row in app.model.annotations if row.get('links', '').startswith('V_')
                   and app.native_path(row) is not None)
        source = Path(app.model.db['source']); before = hashlib.sha256(source.read_bytes()).hexdigest()
        fields = local_fields(row); fields['comment'] = 'Commentaire local conservant le chemin.'
        saved = app.store.set_override(row['key'], fields)
        app.refresh_local_annotations()
        edited = app.model.by_key['note:' + saved['id']]
        self.assertEqual(edited['links'], row['links'])
        self.assertEqual(app.native_path(edited).points, app.native_path(row).points)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_personal_route_points_options_and_profile_restart(self):
        from tools.clone_app import Application
        app = self.app; app.edit_enabled.set(True); app.edit_mode_changed()
        x, y = app.map.cx, app.map.cy
        app.start_route(x, y); app.append_route_point(x+5, y+6); app.append_route_point(x+20, y+12)
        app.undo_route_point(); app.finish_route(); self.pump()
        expected = ((round(x, 5), round(y, 5)), (round(x+5, 5), round(y+6, 5)))
        self.assertEqual(app.map.personal_paths[0].points, expected)
        self.assertFalse(app.map.route_editing)
        self.assertEqual(app.store.notes(), [])
        self.close(); self.app = Application(DATA, self.path, offline=True)
        self.app.root.report_callback_exception = lambda kind, value, trace: self.callback_errors.append(value)
        self.pump(); self.app.initial_view(); self.pump()
        self.assertEqual(self.app.map.personal_paths[0].points, expected)
        self.assertEqual((self.app.database_flag_icon.width(), self.app.database_flag_icon.height()), (20, 13))

    def test_legend_style_changes_persist_without_changing_native_category(self):
        from tools.clone_app import Application
        app = self.app; native = dict(app.model.categories[37])
        with patch('tools.clone_reference_ui.colorchooser.askcolor', return_value=((18,52,86), '#123456')):
            app.choose_legend_color(37)
        app.choose_legend_font(37); self.pump()
        dialog = app.font_window
        family = next(w for w in descendants(dialog) if w.winfo_class() == 'TCombobox')
        family.set('Arial')
        size = next(w for w in descendants(dialog) if isinstance(w, tk.Spinbox))
        size.delete(0, 'end'); size.insert(0, '10')
        italic = next(w for w in descendants(dialog) if isinstance(w, tk.Checkbutton) and w.cget('text') == 'Italique')
        if dialog.getvar(italic.cget('variable')): italic.invoke()
        next(w for w in descendants(dialog) if isinstance(w, tk.Checkbutton) and w.cget('text') == 'Gras').invoke()
        next(w for w in descendants(dialog) if isinstance(w, tk.Button) and w.cget('text') == 'OK').invoke()
        self.assertEqual(app.map.category_colors[37], '#123456')
        self.assertEqual(app.map.legend_font(37), ('Arial', 10, 'bold'))
        self.assertEqual(app.model.categories[37], native)
        self.close(); self.app = Application(DATA, self.path, offline=True)
        self.app.root.report_callback_exception = lambda kind, value, trace: self.callback_errors.append(value)
        self.pump(); self.app.initial_view(); self.pump()
        self.assertEqual(self.app.map.category_colors[37], '#123456')
        self.assertEqual(self.app.map.legend_font(37), ('Arial', 10, 'bold'))
        self.app.reset_legend_style(37)
        self.assertNotIn(37, self.app.map.category_colors)
        self.assertNotIn(37, self.app.map.category_fonts)


if __name__ == '__main__': unittest.main()
