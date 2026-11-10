"""User-facing panels and commands aligned with the documented 1.20 interface."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser, font as tkfont
import uuid

from tools.clone_model import folded
from tools.clone_annotation_dialog import local_fields
from tools.map_packs import load_pack, local_file


SHORTCUTS = (
    ('F1 / F2 / F3 / F4', 'Régions / Liste Master / Résultats / Informations'),
    ('Ctrl+F / Ctrl+G / Ctrl+T', 'Nouvelle recherche / Recherche précédente / Région affichée'),
    ('H', 'Afficher ou fermer cette aide'), ('A', 'Afficher ou masquer les annotations'),
    ('+ / − / molette', 'Zoomer / dézoomer'), ('Z / double-clic', 'Échelle 1:1'),
    ('S / L', 'Assombrir la carte / Légendes'), ('F', 'Centrer l’annotation sélectionnée'),
    ('M', 'Ajuster la section de carte courante'), ('Ctrl+clic gauche', 'Sélectionner la région sous le pointeur'),
    ('I / Maj+clic', 'Créer ou modifier une annotation en mode édition'),
    ('Ctrl+C / Ctrl+X / Ctrl+V', 'Copier / Couper / Coller une annotation'),
    ('Ctrl+S', 'Enregistrer les annotations (enregistrement automatique)'),
    ('Échap', 'Désélectionner l’annotation et quitter la sélection de recherche'),
    ('Ctrl+,', 'Préférences'), ('Ctrl+N', 'Ajouter une annotation au centre'),
)


class ReferenceInterface:
    def create_reference_panes(self):
        self.master_pane = tk.Frame(self.panes)
        head = tk.Frame(self.master_pane); head.pack(fill='x')
        tk.Label(head, text='Liste Master').pack(anchor='w', padx=5)
        self.master_filter = tk.StringVar()
        field = tk.Entry(head, textvariable=self.master_filter); field.pack(fill='x', padx=4, pady=4)
        field.bind('<Return>', lambda e: self.populate_master())
        tk.Button(head, text='Filtrer', command=self.populate_master).pack(anchor='e', padx=4)
        listing = tk.Frame(self.master_pane); listing.pack(fill='both', expand=True)
        self.master_tree = ttk.Treeview(listing, show='tree', selectmode='browse', style='Original.Treeview')
        scroll = ttk.Scrollbar(listing, command=self.master_tree.yview)
        scroll.pack(side='right', fill='y'); self.master_tree.configure(yscrollcommand=scroll.set)
        self.master_tree.pack(fill='both', expand=True)
        self.master_tree.bind('<<TreeviewOpen>>', self.expand_master)
        self.master_tree.bind('<<TreeviewSelect>>', self.select_master)
        self.master_tree.bind('<Double-Button-1>', self.master_details)
        self.master_nodes, self.master_records, self.master_more, self.master_current = {}, {}, {}, None
        self.active_pane = 'regions'

    def show_reference_pane(self, name):
        panes = {'regions': self.region_pane, 'master': self.master_pane,
                 'results': self.results_pane, 'details': self.detail_window}
        for frame in panes.values(): frame.pack_forget()
        panes.get(name, self.region_pane).pack(fill='both', expand=True)
        self.active_pane = name
        for index, pane in ((2, 'regions'), (3, 'master'), (4, 'results'), (5, 'details')):
            button = getattr(self, 'icon_buttons', {}).get(index)
            if button is not None: button.configure(relief='sunken' if pane == name else 'flat')
        if name == 'master': self.populate_master()
        if name == 'details': self.update_database_info()

    def invalidate_master(self):
        self.master_current = None

    def populate_master(self):
        identity = (self.mode.get(), self.database.get(), self.master_filter.get(), id(getattr(self.model, 'annotations', None)))
        if self.master_current == identity: return
        self.master_current = identity
        self.master_tree.delete(*self.master_tree.get_children())
        self.master_nodes, self.master_records, self.master_more = {}, {}, {}
        grouped = defaultdict(lambda: defaultdict(list))
        needle = folded(self.master_filter.get())
        rows = (self.forever_by_key.values() if self.mode.get() == 'Modern' else getattr(self.model, 'annotations', []))
        for row in rows:
            if needle and needle not in folded(row['name']): continue
            grouped[row['region']][row['category']].append(row)
        for region, categories in sorted(grouped.items(), key=lambda pair: folded(pair[0])):
            count = sum(map(len, categories.values()))
            parent = self.master_tree.insert('', 'end', text=f'{region} ({count})', image=self.region_tree_icon or '')
            for category, records in sorted(categories.items(), key=lambda pair: folded(self.model.categories.get(pair[0], {}).get('name', ''))):
                title = self.model.categories.get(category, {}).get('name', str(category))
                node = self.master_tree.insert(parent, 'end', text=f'{title} ({len(records)})', image=self.category_icons.get(category, ''))
                self.master_nodes[node] = sorted(records, key=lambda row: folded(row['name']))
                self.master_tree.insert(node, 'end', text='…')

    def expand_master(self, event=None):
        node = self.master_tree.focus()
        records = self.master_nodes.pop(node, None)
        if records is None: return
        self.master_tree.delete(*self.master_tree.get_children(node))
        self.append_master_page(node, records, 0)

    def append_master_page(self, node, records, offset):
        for row in records[offset:offset + 500]:
            iid = self.master_tree.insert(node, 'end', text=row['name'], image=self.category_icons.get(row['category'], ''))
            self.master_records[iid] = row
        end = min(offset + 500, len(records))
        if end < len(records):
            more = self.master_tree.insert(node, 'end', text=f'Afficher les suivants… ({end}/{len(records)})')
            self.master_more[more] = (node, records, end)

    def select_master(self, event=None):
        selection = self.master_tree.selection()
        if selection and selection[0] in self.master_more:
            node, records, offset = self.master_more.pop(selection[0])
            self.master_tree.delete(selection[0]); self.append_master_page(node, records, offset)
        elif selection and selection[0] in self.master_records:
            self.focus_record(self.master_records[selection[0]])

    def master_details(self, event=None):
        selected = self.master_tree.selection()
        if selected and selected[0] in self.master_records: self.show_pane('details')

    def focus_record(self, row):
        tiles = self.map_tiles_by_group.get(row['group_id'])
        if not tiles: return
        self.group, self.tiles = row['group_id'], tiles
        if self.shown_group != self.group:
            self.shown_group = self.group
            records = (self.forever_by_group.get(self.group, []) if self.mode.get() == 'Modern'
                       else self.model.by_group.get(self.group, []))
            self.map.set_scene(tiles, records)
        self.shown_region = None; self.map.region_outline = []
        self.map.region_markers = [dict(iid=key, wx=point[0], wy=point[1])
            for key, point in self.region_centers.items() if self.groups[key][0] == self.group]
        self.regions.selection_remove(*self.regions.selection())
        self.map.selected = row['key']
        category = self.model.categories.get(row['category'], {})
        tier = category.get('zoom_tier', 1)
        minimum = (0, 200, 400)[tier - 1] / 256 if tier in (1, 2, 3) else 0
        self.map.center(row['wx'], row['wy'], max(.2 if self.mode.get() == 'Modern' else .8, minimum))
        self.select_record(row)
        self.refresh_routes()

    def update_database_info(self):
        if not hasattr(self, 'database_info') or not hasattr(self.model, 'annotations'): return
        title = self.model.map_set.get('title', self.mode.get())
        info = f"{title}\nBase : {self.database.get()}\n{len(self.model.annotations):,} annotations · {len(self.model.categories)} catégories\n{len(self.store.notes())} annotations personnelles"
        self.database_info.configure(text=info)

    def bind_reference_shortcuts(self):
        actions = {
            '<F1>': lambda: self.show_pane('regions'), '<F2>': lambda: self.show_pane('master'),
            '<F3>': lambda: self.show_pane('results'), '<F4>': lambda: self.show_pane('details'),
            '<Control-f>': lambda: self.show_search(clear=True), '<Control-g>': self.show_search,
            '<Control-t>': lambda: self.show_search(current=True), '<Control-c>': self.copy_annotation,
            '<Control-x>': lambda: self.copy_annotation(cut=True), '<Control-v>': self.paste_annotation,
            '<Escape>': self.clear_selection, 'h': self.show_help, 'a': self.toggle_annotations,
            's': self.toggle_dim, 'l': self.toggle_legend, 'f': self.center_selection,
            'm': self.fit_section, 'z': lambda: self.map.zoom_to(self.map.one_to_one_scale),
            'i': self.edit_selection, '<plus>': lambda: self.map.zoom_to(self.map.scale * 1.25),
            '<KP_Add>': lambda: self.map.zoom_to(self.map.scale * 1.25),
            '<minus>': lambda: self.map.zoom_to(self.map.scale * .8),
            '<KP_Subtract>': lambda: self.map.zoom_to(self.map.scale * .8),
        }
        for binding, action in actions.items():
            self.root.bind(binding, lambda event, callback=action: self.reference_key(event, callback))
        def close_window(event):
            self.close()
            return 'break'
        self.root.bind('<Alt-F4>', close_window)

    def reference_key(self, event, action):
        if event.state & (8 | 0x20000): return None
        widget = event.widget
        if (isinstance(widget, (tk.Entry, tk.Text, tk.Spinbox, ttk.Entry, ttk.Combobox, ttk.Spinbox))
                and not (event.keysym in ('F1', 'F2', 'F3', 'F4') or (event.state & 4 and event.keysym.lower() in ('f', 'g', 't')))):
            return None
        action()
        return 'break'

    def center_selection(self):
        if self.selection: self.focus_record(self.selection)

    def fit_section(self):
        tile = self.map.tile_at(self.map.cx, self.map.cy)
        if tile:
            self.map.fit_bounds((tile['x'], tile['y'], tile['x'] + tile.get('width', 256), tile['y'] + tile.get('height', 256)))
        else: self.map.fit()

    def clear_selection(self):
        if self.map.route_editing: self.finish_route(); return
        self.map.selected = None; self.selection = None
        self.detail.delete('1.0', 'end'); self.map.schedule()

    def toggle_annotations(self):
        self.map.annotations_visible = not self.map.annotations_visible; self.map.schedule()

    def toggle_paths(self):
        self.map.paths_visible = not self.map.paths_visible; self.map.schedule()

    def show_overview(self):
        self.map.paths_visible = True
        self.map.fit()

    def route_identity(self):
        return dict(dataset=self.model.map_set['id'], database=self.database.get(), group=self.group)

    def refresh_routes(self):
        from tools.clone_paths import DecodedNativePath
        identity = self.route_identity()
        routes = []
        values = self.preferences.get('personal_paths', [])
        if not isinstance(values, list): values = []
        for row in values:
            try:
                if not isinstance(row, dict): continue
                if any(row.get(key) != value for key, value in identity.items()): continue
                points = tuple((float(x), float(y)) for x, y in row['points'])
                if not 1 <= len(points) <= 4096: continue
                if any(not math.isfinite(value) or abs(value) > 2**23 for point in points for value in point): continue
                routes.append(DecodedNativePath('V', points, False, bool(row.get('always_visible')),
                    (51, 85, 102, 136, 170, 187, 204, 221, 238, 255)[row.get('opacity', 8)]))
            except (ValueError, TypeError, KeyError, IndexError): continue
        self.map.personal_paths = routes; self.map.schedule()

    def start_route(self, wx, wy):
        if not self.can_edit(): return
        rows = self.preferences.setdefault('personal_paths', [])
        if not isinstance(rows, list):
            self.status.set('Les chemins du profil sont illisibles ; données conservées sans modification.'); return
        if len(rows) >= 64:
            messagebox.showinfo('Chemins personnels', 'Le profil contient déjà le maximum de 64 chemins personnels.', parent=self.root); return
        self.active_route = str(uuid.uuid4())
        rows.append(dict(self.route_identity(), id=self.active_route, points=[], opacity=8, always_visible=True))
        self.map.route_editing = True; self.map.paths_visible = True
        self.append_route_point(wx, wy)
        self.status.set('Chemin : cliquez pour ajouter un point. Double-clic ou Échap termine le chemin ; clic droit propose Annuler le dernier point.')

    def append_route_point(self, wx, wy):
        if self.consultation_blocked(): return
        rows = self.preferences.get('personal_paths', [])
        row = next((row for row in rows if row.get('id') == getattr(self, 'active_route', None)), None)
        if row is None: return
        if sum(len(route.get('points', [])) for route in rows) >= 4096:
            self.status.set('Limite de 4096 points atteinte dans le profil.'); self.finish_route(); return
        point = [round(float(wx), 5), round(float(wy), 5)]
        if not row['points'] or row['points'][-1] != point: row['points'].append(point)
        self.save_preferences(); self.refresh_routes()

    def undo_route_point(self):
        if self.consultation_blocked(): return
        row = next((r for r in self.preferences.get('personal_paths', []) if r.get('id') == getattr(self, 'active_route', None)), None)
        if row and row['points']: row['points'].pop(); self.save_preferences(); self.refresh_routes()

    def finish_route(self):
        if self.consultation_blocked(): return
        self.map.route_editing = False
        self.save_preferences(); self.refresh_routes()
        self.status.set('Chemin personnel enregistré dans le profil et inclus dans ses sauvegardes.')

    def route_options(self):
        if self.consultation_blocked(): return
        rows = self.preferences.get('personal_paths', [])
        identity = self.route_identity()
        row = next((r for r in reversed(rows) if all(r.get(key) == value for key, value in identity.items())), None)
        if row is None:
            self.status.set('Créez d’abord un chemin personnel par clic droit sur la carte.'); return
        dialog, created = self._dialog('route_window', 'Options du chemin', '280x145')
        if not created: return
        opacity = tk.IntVar(value=row.get('opacity', 8)); visible = tk.BooleanVar(value=row.get('always_visible', True))
        line = tk.Frame(dialog); line.pack(fill='x', padx=12, pady=10)
        tk.Label(line, text='Opacité (0–9) :').pack(side='left')
        tk.Spinbox(line, from_=0, to=9, textvariable=opacity, width=5).pack(side='right')
        tk.Checkbutton(dialog, text='Afficher aussi en vue générale', variable=visible).pack(anchor='w', padx=12)
        def save():
            try:
                value = opacity.get()
                if not 0 <= value <= 9: raise ValueError()
            except (ValueError, tk.TclError): return
            row.update(opacity=value, always_visible=visible.get()); self.save_preferences(); self.refresh_routes(); dialog.destroy()
        tk.Button(dialog, text='OK', command=save, width=10).pack(anchor='e', padx=12, pady=10)
        self.center_dialog(dialog); self.apply_theme()

    def edit_selection(self):
        if self.selection: self.edit_note(self.selection)
        else: self.add_at_center()

    def copy_annotation(self, *, cut=False):
        if not self.selection:
            self.status.set('Sélectionnez une annotation à copier.'); return
        if cut and not self.can_edit(): return
        row = self.selection
        payload = {name: row.get(name, default) for name, default in
            (('name', ''), ('comment', ''), ('category', 37), ('min_level', 0), ('max_level', 0))}
        payload['tags'] = row.get('tags') or '; '.join(row.get('property_names', []))
        flags = row.get('flags', '')
        payload['flags'] = flags if isinstance(flags, str) else json.dumps(flags)
        document = dict(format='wcf-annotation-clipboard-v1', data=payload, dataset=self.model.map_set['id'], database=self.database.get())
        self.root.clipboard_clear(); self.root.clipboard_append(json.dumps(document, ensure_ascii=False))
        if cut:
            if row.get('note_id'): self.store.delete_note(row['note_id'], expected_revision=row.get('revision'))
            else: self.store.set_override(row['key'], local_fields(row), hidden=True)
            self.refresh_local_annotations()
        self.status.set('Annotation coupée. La source masquée reste restaurable dans le profil.' if cut
                        else 'Annotation copiée. Clic droit sur la destination, puis Coller.')

    def paste_annotation(self, target=None):
        if not self.can_edit(): return
        try:
            raw = self.root.clipboard_get()
            if len(raw) > 80_000: raise ValueError('Presse-papiers trop volumineux.')
            document = json.loads(raw)
            if (document.get('format') != 'wcf-annotation-clipboard-v1' or
                document.get('dataset') != self.model.map_set['id'] or document.get('database') != self.database.get()):
                raise ValueError('Copiez une annotation du même jeu de données et de la même base.')
            tile, wx, wy = target or (self.map.tile_at(self.map.cx, self.map.cy), self.map.cx, self.map.cy)
            if not tile: raise ValueError('Choisissez un point sur une carte disponible.')
            values = dict(document['data'], map_id=tile['id'], x=max(0, min(65535, round((wx - tile['x']) * 256))),
                          y=max(0, min(65535, round((wy - tile['y']) * 256))),
                          source_ref=self.model.personal_prefix + str(uuid.uuid4()))
            note_id = self.store.add_note(values)
            self.refresh_local_annotations(); self.select_saved_note(note_id)
            self.status.set('Annotation collée et enregistrée.')
        except (tk.TclError, ValueError, TypeError, KeyError) as error:
            messagebox.showerror('Coller une annotation', str(error), parent=self.root)

    def _dialog(self, key, title, size):
        previous = getattr(self, key, None)
        if previous is not None and previous.winfo_exists():
            previous.deiconify(); previous.lift(); return previous, False
        dialog = tk.Toplevel(self.root); dialog.title(title); dialog.geometry(size)
        width, height = size.split('x', 1)
        dialog._wcf_requested_size = (int(width), int(height))
        dialog.transient(self.root); dialog.bind('<Escape>', lambda event: dialog.destroy())
        setattr(self, key, dialog)
        return dialog, True

    def show_help(self):
        previous = getattr(self, 'help_window', None)
        if previous is not None and previous.winfo_exists(): previous.destroy(); return
        dialog, _ = self._dialog('help_window', 'Aide — raccourcis clavier', '620x540')
        tk.Label(dialog, text='WoWCarto Forever — Aide', font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=14, pady=12)
        body = tk.Text(dialog, wrap='word', padx=12, pady=8)
        body.pack(fill='both', expand=True, padx=8)
        for keys, text in SHORTCUTS: body.insert('end', f'{keys}\n{text}\n\n')
        body.insert('end', 'Choisissez une région à droite, faites glisser la carte et zoomez avec la molette.\n'
                    'Pour ajouter ou modifier une annotation, activez le crayon « Mode édition ».\n'
                    'Les annotations sont enregistrées automatiquement et restent conservées après désinstallation.\n'
                    'Les données Legacy et Forever sont proposées avec leurs limites dans Informations.\n')
        body.configure(state='disabled')
        tk.Button(dialog, text='Fermer', command=dialog.destroy).pack(anchor='e', padx=12, pady=10)
        self.center_dialog(dialog); self.apply_theme()

    def show_about(self):
        dialog, created = self._dialog('about_window', 'À propos de WoWCarto Forever', '465x430')
        if not created: return
        tabs = ttk.Notebook(dialog); tabs.pack(fill='both', expand=True, padx=8, pady=8)
        texts = [ ('Infos', f'WoWCarto Forever {self.version}\n\nCartographie et annotations locales.\n\n'
            'Interface inspirée de WoWCartographe 1.20 ; client indépendant.\n'
            'Les annotations personnelles sont conservées dans votre profil Windows.\n\n' + str(self.store.path.parent)),
            ('Crédits', 'WoWCartographe original : tixu, © 2004–2009.\n'
             'Ressources et bases historiques : leurs auteurs respectifs.\n'
             'World of Warcraft et ses cartes : Blizzard Entertainment.\n\n'
             'Ce paquet local utilise les ressources déjà présentes sur cette machine. '
             'Leur présence ne constitue pas une autorisation de redistribution.\n\n'
             'Client : Python, Tk, Pillow et SQLite.\nDéveloppement WoWCarto Forever : projet de Jordan.')]
        for name, text in texts:
            frame = tk.Frame(tabs); tabs.add(frame, text=name)
            field = tk.Text(frame, wrap='word', padx=12, pady=12); field.pack(fill='both', expand=True)
            field.insert('1.0', text); field.configure(state='disabled')
        tk.Button(dialog, text='OK', command=dialog.destroy).pack(anchor='e', padx=12, pady=8)
        self.center_dialog(dialog); self.apply_theme()

    def show_reference_preferences(self):
        dialog, created = self._dialog('preferences_window', 'Préférences et Options', '520x530')
        if not created: return
        tabs = ttk.Notebook(dialog); tabs.pack(fill='both', expand=True, padx=8, pady=8)
        general, display, categories = (tk.Frame(tabs, padx=12, pady=12) for _ in range(3))
        tabs.add(general, text='Général'); tabs.add(display, text='Affichage'); tabs.add(categories, text='Légendes')
        def combo(parent, title, variable, values, command):
            tk.Label(parent, text=title).pack(anchor='w', pady=(6, 2))
            field = ttk.Combobox(parent, textvariable=variable, values=values, state='readonly')
            field.pack(fill='x'); field.bind('<<ComboboxSelected>>', lambda e: command())
        combo(general, 'Interface', self.interface, ('Legacy', 'Modern'), self.change_interface)
        combo(general, 'Langue de la base', self.database, self.languages, self.change_database)
        combo(general, 'Langue de l’interface', self.ui_language, ('fr', 'en'), self.change_ui_language)
        combo(general, 'Base autorisée pour l’édition', self.edit_database, self.languages, self.edit_database_changed)
        tk.Checkbutton(general, text='Mode édition', variable=self.edit_enabled, command=self.edit_mode_changed).pack(anchor='w', pady=8)
        tk.Label(general, text='Profil personnel\n' + str(self.store.path.parent), wraplength=450, justify='left').pack(anchor='w', pady=8)
        tk.Button(general, text='Sauvegarder le profil…', command=self.backup_profile).pack(fill='x', pady=2)
        tk.Button(general, text='Restaurer une sauvegarde…', command=self.restore_profile).pack(fill='x', pady=2)
        tk.Checkbutton(display, text='Thème sombre', variable=self.dark_theme, command=self.change_theme).pack(anchor='w')
        for title, attribute in [('Afficher les annotations', 'annotations_visible'), ('Afficher les légendes', 'legend'),
                                  ('Afficher les chemins', 'paths_visible'), ('Assombrir la carte', 'dim'),
                                  ('Colorer les mobs selon le niveau du personnage', 'color_by_level'),
                                  ('Cartes en haute définition disponibles', 'high')]:
            variable = tk.BooleanVar(value=getattr(self.map, attribute))
            def update(var=variable, name=attribute): setattr(self.map, name, var.get()); self.map.schedule()
            tk.Checkbutton(display, text=title, variable=variable, command=update).pack(anchor='w', pady=4)
        tk.Label(display, text='Taille des marqueurs').pack(anchor='w', pady=(12, 4))
        marker = tk.StringVar(value='Confort (×2)' if self.map.marker_scale == 2 else 'Compact (×1)')
        scale = ttk.Combobox(display, textvariable=marker, values=('Compact (×1)', 'Confort (×2)'), state='readonly')
        scale.pack(fill='x')
        def resize_markers(event):
            self.map.marker_scale = 1 if scale.current() == 0 else 2
            self.preferences['marker_scale'] = self.map.marker_scale
            self.load_category_icons(); self.map.schedule()
        scale.bind('<<ComboboxSelected>>', resize_markers)
        tk.Label(display, text='Les icônes de carte conservent leurs formes et couleurs.\nLeur taille est indépendante du zoom de la carte.', justify='left', wraplength=440).pack(anchor='w', pady=8)
        tk.Label(categories, text='Catégories de la base active').pack(anchor='w')
        listing = tk.Listbox(categories, selectmode='multiple', exportselection=False); listing.pack(fill='both', expand=True, pady=8)
        rows = sorted(self.model.categories.items(), key=lambda item: folded(item[1]['name']))
        for index, (ident, category) in enumerate(rows):
            listing.insert('end', category['name'])
            if self.map.category_filter is None or ident in self.map.category_filter: listing.selection_set(index)
        buttons = tk.Frame(categories); buttons.pack(fill='x')
        tk.Button(buttons, text='Toutes', command=lambda: listing.selection_set(0, 'end')).pack(side='left')
        tk.Button(buttons, text='Aucune', command=lambda: listing.selection_clear(0, 'end')).pack(side='left', padx=4)
        def apply_categories():
            self.map.category_filter = {rows[i][0] for i in listing.curselection()}; self.map.schedule()
        tk.Button(buttons, text='Appliquer les catégories', command=apply_categories).pack(side='right')
        tk.Label(categories, text='Personnaliser une légende :').pack(anchor='w', pady=(10, 3))
        choice = ttk.Combobox(categories, values=[row['name'] for ident, row in rows], state='readonly')
        choice.pack(fill='x'); choice.current(0)
        customize = tk.Frame(categories); customize.pack(fill='x', pady=4)
        def category_id(): return rows[max(choice.current(), 0)][0]
        tk.Button(customize, text='Couleur…', command=lambda: self.choose_legend_color(category_id())).pack(side='left')
        tk.Button(customize, text='Police…', command=lambda: self.choose_legend_font(category_id())).pack(side='left', padx=5)
        tk.Button(customize, text='Rétablir', command=lambda: self.reset_legend_style(category_id())).pack(side='right')
        footer = tk.Frame(dialog); footer.pack(fill='x', padx=12, pady=8)
        tk.Label(footer, text='Les réglages sont appliqués immédiatement.').pack(side='left')
        def close(): self.capture_session(); self.save_preferences(); dialog.destroy()
        tk.Button(footer, text='Fermer', command=close, width=10).pack(side='right')
        dialog.protocol('WM_DELETE_WINDOW', close)
        self.center_dialog(dialog); self.apply_theme()

    def choose_legend_color(self, ident):
        initial = self.map.category_colors.get(ident, self.model.categories[ident]['color_rgb'])
        chosen = colorchooser.askcolor(color=initial, title='Couleur de la légende', parent=self.root)[1]
        if chosen:
            self.map.category_colors[ident] = chosen
            self.preferences.setdefault('legend_colors', {})[str(ident)] = chosen
            self.save_preferences(); self.map.schedule()

    def reset_legend_style(self, ident):
        self.map.category_colors.pop(ident, None); self.map.category_fonts.pop(ident, None)
        self.preferences.setdefault('legend_colors', {}).pop(str(ident), None)
        self.preferences.setdefault('legend_fonts', {}).pop(str(ident), None)
        self.save_preferences(); self.map.schedule()

    def choose_legend_font(self, ident):
        dialog, created = self._dialog('font_window', 'Police de la légende', '420x245')
        if not created: return
        family, size, style = self.map.legend_font(ident)
        name = tk.StringVar(value=family); height = tk.IntVar(value=size)
        bold = tk.BooleanVar(value='bold' in style); italic = tk.BooleanVar(value='italic' in style)
        body = tk.Frame(dialog, padx=14, pady=12); body.pack(fill='both', expand=True)
        ttk.Combobox(body, textvariable=name, values=sorted(set(tkfont.families(self.root))), state='readonly').pack(fill='x', pady=4)
        tk.Spinbox(body, textvariable=height, from_=4, to=48, width=6).pack(anchor='w', pady=4)
        tk.Checkbutton(body, text='Gras', variable=bold).pack(anchor='w')
        tk.Checkbutton(body, text='Italique', variable=italic).pack(anchor='w')
        def save():
            try:
                point = height.get()
                if not 4 <= point <= 48: return
                styles = ' '.join(value for value, active in (('bold', bold.get()), ('italic', italic.get())) if active) or 'normal'
                value = (name.get(), point, styles)
                self.map.category_fonts[ident] = value
                self.preferences.setdefault('legend_fonts', {})[str(ident)] = list(value)
                self.save_preferences(); self.map.schedule(); dialog.destroy()
            except tk.TclError: return
        tk.Button(body, text='OK', command=save, width=10).pack(anchor='e', pady=8)
        self.center_dialog(dialog); self.apply_theme()

    def show_update_dialog(self):
        dialog, created = self._dialog('update_window', 'Mise à jour des bases', '490x430')
        if not created: return
        tk.Label(dialog, text='Les cartes et vos annotations restent disponibles hors ligne.', wraplength=450, justify='left').pack(anchor='w', padx=12, pady=12)
        tabs = ttk.Notebook(dialog); tabs.pack(fill='both', expand=True, padx=8)
        connection = tk.Frame(tabs, padx=12, pady=12); options = tk.Frame(tabs, padx=12, pady=12)
        tabs.add(connection, text='Connexion'); tabs.add(options, text='Options')
        tk.Label(connection, text='La synchronisation récupère les données communautaires.\nLe partage de vos annotations demande une action explicite.', justify='left', wraplength=440).pack(anchor='w')
        tk.Label(connection, textvariable=self.status, wraplength=440, justify='left').pack(anchor='w', pady=12)
        button = tk.Button(connection, text='Vérifier les mises à jour', command=self.sync, state='disabled' if self.offline else 'normal')
        button.pack(anchor='w', pady=8)
        if self.offline: tk.Label(connection, text='Mode hors ligne activé pour cette session.').pack(anchor='w')
        tk.Label(options, text='Connexion sécurisée HTTPS avec le proxy configuré dans Windows.\n'
                 'Les anciens modes HTTP et FTP du 1.20 ne sont pas utilisés.\n\n'
                 'Aucun compte ni mot de passe n’est nécessaire pour consulter les cartes locales.', wraplength=430, justify='left').pack(anchor='w')
        tk.Button(dialog, text='Fermer', command=dialog.destroy).pack(anchor='e', padx=12, pady=8)
        self.center_dialog(dialog); self.apply_theme()

    def show_resource_manager(self):
        dialog, created = self._dialog('resources_window', 'Cartes et données locales', '650x400')
        if not created: return
        left = tk.Frame(dialog, width=235, padx=12, pady=12); left.pack(side='left', fill='y'); left.pack_propagate(False)
        tk.Label(left, text='Préparation des cartes', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        tk.Label(left, text='Les fonds de carte de ce paquet sont déjà préparés.\n\n'
                 'Vérifier contrôle les fichiers locaux sans modifier vos annotations.\n\n'
                 'Pour ajouter un autre ensemble préparé, choisissez son dossier de données. '
                 'Les archives du jeu ne sont jamais modifiées.', wraplength=210, justify='left').pack(anchor='w', pady=10)
        right = tk.Frame(dialog, padx=10, pady=12); right.pack(fill='both', expand=True)
        path = tk.Entry(right); path.insert(0, str(self.data)); path.configure(state='readonly'); path.pack(fill='x')
        listing = ttk.Treeview(right, columns=('state',), show='tree headings', height=8)
        listing.heading('#0', text='Jeu de données'); listing.heading('state', text='État')
        listing.column('#0', width=240); listing.column('state', width=115); listing.pack(fill='both', expand=True, pady=8)
        for spec in self.model.sets: listing.insert('', 'end', text=spec['title'], values=('Installé',))
        progress = ttk.Progressbar(right, mode='indeterminate'); progress.pack(fill='x')
        result = tk.StringVar(value='Prêt.'); tk.Label(right, textvariable=result, wraplength=360, justify='left').pack(anchor='w', pady=6)
        buttons = tk.Frame(right); buttons.pack(fill='x')
        def verify():
            verify_button.configure(state='disabled'); progress.start()
            def worker():
                try:
                    packs = {name for spec in self.model.sets for name in
                        [*spec.get('packs', []), *[spec[k] for k in ('terrain_pack', 'legacy_pack') if k in spec]]}
                    count = sum(len(load_pack(local_file(self.data, name), verify=True)['maps']) for name in packs)
                    message = f'{count} cartes vérifiées. Vos annotations sont intactes.'
                except (OSError, ValueError) as error: message = 'Vérification : ' + str(error)
                def complete():
                    if dialog.winfo_exists(): result.set(message); progress.stop(); verify_button.configure(state='normal')
                self.root.after(0, complete)
            threading.Thread(target=worker, daemon=True).start()
        verify_button = tk.Button(buttons, text='Vérifier les cartes', command=verify); verify_button.pack(side='left')
        tk.Button(buttons, text='Choisir un dossier…', command=self.choose_data_directory).pack(side='left', padx=4)
        tk.Button(buttons, text='Fermer', command=dialog.destroy).pack(side='right')
        self.center_dialog(dialog); self.apply_theme()

    def choose_data_directory(self):
        path = filedialog.askdirectory(parent=self.root, title='Choisir un dossier de données WoWCarto Forever')
        if not path: return
        try:
            directory = Path(path).resolve()
            catalog = json.loads((directory / 'catalog.json').read_text(encoding='utf-8'))
            if catalog.get('format') != 'wcf-clone-catalog-v1' or not catalog.get('sets'):
                raise ValueError('Ce dossier ne contient pas de cartes WoWCarto Forever préparées.')
            self.preferences['data_directory'] = str(directory); self.save_preferences()
            messagebox.showinfo('Données locales', 'Le nouveau dossier sera utilisé au prochain lancement.', parent=self.root)
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror('Données locales', str(error), parent=self.root)

    def show_welcome(self):
        dialog, created = self._dialog('welcome_window', 'Bienvenue dans WoWCarto Forever', '540x410')
        if not created: return
        tk.Label(dialog, text='Vos cartes sont prêtes.', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=22, pady=(20, 12))
        tk.Label(dialog, text='1. Choisissez une région dans la liste à droite.\n\n'
                 '2. Faites glisser la carte ; utilisez la molette pour zoomer.\n\n'
                 '3. Ctrl+F recherche un nom. Le crayon active vos annotations.\n\n'
                 'Vos notes sont enregistrées automatiquement sur ce PC.\n'
                 'Vous pouvez sauvegarder le profil depuis Préférences.\n\n'
                 'La base 1.20 est proposée au départ. Legacy et Forever restent\n'
                 'accessibles dans le menu ; leurs limites figurent dans Informations.',
                 justify='left', wraplength=490).pack(anchor='w', padx=22)
        def finish():
            self.preferences['welcome_seen'] = True; self.preferences['data_notice_seen'] = True
            self.save_preferences(); dialog.destroy()
        tk.Button(dialog, text='Commencer', command=finish, width=16).pack(anchor='e', padx=22, pady=16)
        dialog.protocol('WM_DELETE_WINDOW', finish)
        self.center_dialog(dialog); self.apply_theme()
