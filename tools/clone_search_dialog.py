"""Two-column reference search dialog with persistent checkbox criteria."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox

from tools.clone_model import folded
from tools.clone_regions import decode_region_outline


FILTER_FIELDS = ('categories', 'properties', 'continents', 'regions')
OPTION_FIELDS = ('name', 'comment', 'categories', 'properties', 'continents', 'regions',
                 'minimum', 'maximum', 'local_only', 'group')


def portable(value):
    if isinstance(value, dict): return {key: portable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)): return [portable(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)): return [portable(item) for item in value]
    return value


def value_key(value):
    return json.dumps(portable(value), sort_keys=True, ensure_ascii=False, allow_nan=False)


def saved_options(options):
    result = {key: portable(value) for key, value in options.items() if key in OPTION_FIELDS}
    # A JSON round trip also detaches mutable region coordinates from the UI.
    return json.loads(value_key(result))


def has_filter(options):
    # Empty property/region lists mean "no restriction" to Model.search.
    return (any(options.get(key) is not None for key in ('categories', 'continents', 'minimum', 'maximum', 'group'))
            or bool(options.get('properties') or options.get('regions') or options.get('local_only')))


class SearchDialog(tk.Toplevel):
    def __init__(self, app, *, clear=False, current=False):
        super().__init__(app.root)
        self.app = app
        self.tr = getattr(app, 'tr', lambda text: text)
        self._identity = self.identity()
        self._loading = False
        self._traces = []
        self._focus_after = None
        self.expanded = False
        self.title(self.tr('Recherche'))
        self.geometry('540x350')
        self.minsize(540, 350)
        self.transient(app.root)
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        if clear:
            self.remember(app.query.get(), getattr(app, 'search_options', {}))
            app.query.set('')
            app.search_options = {}
        self.entries = []
        self.region_labels = {}
        self._make_entries()
        self.criteria = {field: {} for field in FILTER_FIELDS}
        self._explicit_empty = set()
        self.group = None
        self.names = tk.BooleanVar(self, True)
        self.comments = tk.BooleanVar(self, False)
        self.use_level = tk.BooleanVar(self, False)
        self.minimum = tk.StringVar(self, '5')
        self.maximum = tk.StringVar(self, '5')
        self.current_zone = tk.BooleanVar(self, current)
        self.local_only = tk.BooleanVar(self, False)
        self.filter_text = tk.StringVar(self)

        main = tk.Frame(self, padx=5, pady=5)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=1, uniform='columns')
        main.columnconfigure(1, weight=1, uniform='columns')
        main.rowconfigure(0, weight=1)
        left = tk.Frame(main); left.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        right = tk.Frame(main); right.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        left.columnconfigure(0, weight=1); left.rowconfigure(5, weight=1)
        right.columnconfigure(0, weight=1); right.rowconfigure(3, weight=1)

        where = tk.Frame(left); where.grid(row=0, column=0, sticky='ew')
        tk.Label(where, text=self.tr('Chercher dans:')).pack(side='left')
        tk.Checkbutton(where, text=self.tr('Nom'), variable=self.names).pack(side='left')
        tk.Checkbutton(where, text=self.tr('Commentaires'), variable=self.comments).pack(side='left')
        self.entry = tk.Entry(left, textvariable=app.query)
        self.entry.grid(row=1, column=0, sticky='ew', pady=(2, 4))
        levels = tk.Frame(left); levels.grid(row=2, column=0, sticky='ew')
        tk.Checkbutton(levels, text=self.tr('Niveau [min/max]'), variable=self.use_level).pack(side='left')
        tk.Entry(levels, textvariable=self.maximum, width=6).pack(side='right')
        tk.Entry(levels, textvariable=self.minimum, width=6).pack(side='right', padx=(3, 5))
        self.current_check = tk.Checkbutton(left, text=self.tr('Limiter à la région affichée'),
                                            variable=self.current_zone)
        self.current_check.grid(row=3, column=0, sticky='w')
        if not current: self.current_check.grid_remove()
        filter_row = tk.Frame(left); filter_row.grid(row=4, column=0, sticky='ew', pady=(3, 4))
        tk.Label(filter_row, text=self.tr('Filtre'), width=9, anchor='w').pack(side='left')
        tk.Entry(filter_row, textvariable=self.filter_text).pack(side='left', fill='x', expand=True)
        criteria_frame = tk.Frame(left); criteria_frame.grid(row=5, column=0, sticky='nsew')
        self.tree = ttk.Treeview(criteria_frame, show='tree', selectmode='browse',
                                 style='Search.Criteria.Treeview')
        scrollbar = ttk.Scrollbar(criteria_frame, command=self.tree.yview)
        scrollbar.pack(side='right', fill='y'); self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Button-1>', self._click)
        self.tree.bind('<space>', self._space)
        controls = tk.Frame(left); controls.grid(row=6, column=0, sticky='ew', pady=(5, 0))
        tk.Button(controls, text=self.tr('Initialiser les paramètres'), command=self.reset).pack(side='left')
        self.options_menu = tk.Menu(self, tearoff=False)
        self.options_menu.add_command(label=self.tr('Développer les filtres'), command=lambda: self.set_expanded(True))
        self.options_menu.add_command(label=self.tr('Réduire l’arbre'), command=lambda: self.set_expanded(False))
        self.options_menu.add_separator()
        self.options_menu.add_command(label=self.tr('Effacer les critères'), command=self.reset)
        tk.Menubutton(controls, text=self.tr('Options'), relief='raised', menu=self.options_menu,
                      width=8).pack(side='right')

        tk.Label(right, text=self.tr('Paramètres de recherche actuels'), anchor='w').grid(row=0, column=0, sticky='ew')
        summary_frame = tk.Frame(right); summary_frame.grid(row=1, column=0, sticky='ew', pady=(4, 5))
        self.summary = tk.Text(summary_frame, height=5, width=25, wrap='word', state='disabled')
        summary_scroll = ttk.Scrollbar(summary_frame, command=self.summary.yview)
        summary_scroll.pack(side='right', fill='y'); self.summary.configure(yscrollcommand=summary_scroll.set)
        self.summary.pack(fill='both', expand=True)
        tk.Label(right, text=self.tr('Historique des recherches'), anchor='w').grid(row=2, column=0, sticky='ew')
        history_frame = tk.Frame(right); history_frame.grid(row=3, column=0, sticky='nsew', pady=(4, 0))
        self.history = ttk.Treeview(history_frame, show='tree', selectmode='browse', height=5)
        history_scroll = ttk.Scrollbar(history_frame, command=self.history.yview)
        history_scroll.pack(side='right', fill='y'); self.history.configure(yscrollcommand=history_scroll.set)
        self.history.pack(fill='both', expand=True)
        self.history.bind('<<TreeviewSelect>>', self._recall_selected)
        self.history.bind('<Double-Button-1>', lambda event: self.run())
        buttons = tk.Frame(right); buttons.grid(row=4, column=0, sticky='ew', pady=(5, 0))
        tk.Button(buttons, text=self.tr('Chercher'), width=9, command=self.run).pack(side='right')
        tk.Button(buttons, text=self.tr('Annuler'), width=9, command=self.destroy).pack(side='right', padx=(0, 5))

        self.load_options(getattr(app, 'search_options', {}))
        self.current_zone.set(current)
        self.render_tree()
        self.render_history()
        for variable in (app.query, self.names, self.comments, self.use_level, self.minimum,
                         self.maximum, self.current_zone, self.local_only):
            self._traces.append((variable, variable.trace_add('write', self.update_summary)))
        self._traces.append((self.filter_text, self.filter_text.trace_add('write', self.render_tree)))
        self.bind('<Return>', self._enter)
        self.bind('<Escape>', self._escape)
        if callable(getattr(app, 'apply_ui_language', None)): app.apply_ui_language()
        if callable(getattr(app, 'apply_theme', None)): app.apply_theme()
        theme = getattr(app, 'dark_theme', None)
        dark = bool(theme.get()) if theme is not None else False
        style = ttk.Style(self)
        style.configure('Search.Criteria.Treeview', background='#343a43' if dark else '#808080',
                        fieldbackground='#343a43' if dark else '#808080', foreground='white', rowheight=18)
        self.update_summary()
        if callable(getattr(app, 'center_dialog', None)): app.center_dialog(self)
        self._focus_after = self.after_idle(self._focus_entry)

    def identity(self):
        return dict(mode=self.app.mode.get(), database=self.app.database.get())

    def _make_entries(self):
        for ident, row in sorted(self.app.model.categories.items(), key=lambda item: folded(item[1]['name'])):
            self.entries.append((f'category:{ident}', 'categories', ident, row['name'], ident, None))
        for ident, row in sorted(self.app.model.db.get('flags', {}).items(), key=lambda item: folded(item[1]['name'])):
            if row.get('name'):
                self.entries.append((f'property:{ident}', 'properties', row['name'], row['name'], None,
                                     f"property:{row.get('parent') or 0}"))
        for row in sorted(self.app.model.db.get('continents', []), key=lambda item: folded(item['name'])):
            self.entries.append((f"continent:{row['id']}", 'continents', row['id'], row['name'], None, None))
        for row in self.app.model.geographic_regions():
            outline = decode_region_outline(row)
            if outline:
                value = [row['group_id'], portable(outline)]
                self.region_labels[value_key(value)] = row['name']
                self.entries.append((f"region:{row['id']}", 'regions', value, row['name'], 18, None))

    def load_options(self, options):
        self._loading = True
        for field in FILTER_FIELDS:
            values = options.get(field)
            self.criteria[field] = {value_key(value): portable(value) for value in (values or [])}
            self._explicit_empty.discard(field)
            if values is not None and not values: self._explicit_empty.add(field)
        self.group = options.get('group')
        self.names.set(bool(options.get('name', True)))
        self.comments.set(bool(options.get('comment', False)))
        active = options.get('minimum') is not None or options.get('maximum') is not None
        self.use_level.set(active)
        for variable, key in ((self.minimum, 'minimum'), (self.maximum, 'maximum')):
            variable.set(str(options[key]) if options.get(key) is not None else '' if active else '5')
        self.local_only.set(bool(options.get('local_only', False)))
        self._loading = False

    def current_options(self):
        minimum = maximum = None
        if self.use_level.get():
            try:
                minimum = int(self.minimum.get()) if self.minimum.get().strip() else None
                maximum = int(self.maximum.get()) if self.maximum.get().strip() else None
            except ValueError:
                raise ValueError(self.tr('Les niveaux doivent être des nombres.')) from None
            if (minimum is None and maximum is None or
                any(value is not None and not 0 <= value <= 65535 for value in (minimum, maximum)) or
                minimum is not None and maximum is not None and minimum > maximum):
                raise ValueError(self.tr('Plage de niveaux invalide.'))
        result = dict(name=self.names.get(), comment=self.comments.get(), minimum=minimum,
                      maximum=maximum, local_only=self.local_only.get())
        for field in FILTER_FIELDS:
            result[field] = list(self.criteria[field].values()) or ([] if field in self._explicit_empty else None)
        if self.group is not None: result['group'] = self.group
        if self.current_zone.get():
            native = self.app.region_native_ids.get(self.app.shown_region)
            region = next((row for row in self.app.model.geographic_regions() if row['id'] == native), None)
            outline = decode_region_outline(region) if region else None
            if not outline: raise ValueError(self.tr('Sélectionnez une région disposant d’un contour.'))
            result['regions'] = [[region['group_id'], portable(outline)]]
        return result

    def render_tree(self, *_):
        opened = {iid for iid in self.tree.get_children() if self.tree.item(iid, 'open')} if hasattr(self, 'roots') else set()
        self.tree.delete(*self.tree.get_children())
        self.roots = {field: self.tree.insert('', 'end', iid='root:' + field, text=self.tr(label),
                                           open='root:' + field in opened or bool(self.filter_text.get()))
                      for field, label in (('categories', 'Catégories'), ('properties', 'Tags'),
                                           ('continents', 'Continents'), ('regions', 'Régions'))}
        self.item_values, self.item_labels = {}, {}
        needle = folded(self.filter_text.get())
        by_id = {entry[0]: entry for entry in self.entries}
        visible = {entry[0] for entry in self.entries if not needle or needle in folded(entry[3])}
        for iid in list(visible):
            parent = by_id[iid][5]
            seen = set()
            while parent in by_id and parent not in seen:
                visible.add(parent); seen.add(parent); parent = by_id[parent][5]
        pending = [entry for entry in self.entries if entry[0] in visible]
        while pending:
            progress = False
            for entry in pending[:]:
                iid, field, value, label, icon_id, parent = entry
                if parent in visible and not self.tree.exists(parent): continue
                parent = parent if parent in visible and self.tree.exists(parent) else self.roots[field]
                icon = getattr(self.app, 'category_icons', {}).get(icon_id, '')
                self.tree.insert(parent, 'end', iid=iid, text=self._checked_text(field, value, label), image=icon,
                                 open=bool(needle))
                self.item_values[iid] = field, value; self.item_labels[iid] = label
                pending.remove(entry); progress = True
            if not progress:
                # Malformed cyclic property parents cannot prevent the dialog opening.
                pending = [(iid, field, value, label, icon, None) for iid, field, value, label, icon, parent in pending]
        self.tree.insert('', 'end', iid='local', text=('☑ ' if self.local_only.get() else '☐ ') + self.tr('Ajouts Locaux'))
        self.update_summary()

    def _checked_text(self, field, value, label):
        return ('☑ ' if value_key(value) in self.criteria[field] else '☐ ') + label

    def toggle(self, iid):
        if iid == 'local': self.local_only.set(not self.local_only.get())
        elif iid in self.item_values:
            field, value = self.item_values[iid]; key = value_key(value)
            if key in self.criteria[field]: self.criteria[field].pop(key)
            else: self.criteria[field][key] = portable(value)
            self._explicit_empty.discard(field)
        elif iid in self.roots.values():
            self.tree.item(iid, open=not self.tree.item(iid, 'open')); return
        for item, (field, value) in self.item_values.items():
            self.tree.item(item, text=self._checked_text(field, value, self.item_labels[item]))
        self.tree.item('local', text=('☑ ' if self.local_only.get() else '☐ ') + self.tr('Ajouts Locaux'))
        self.update_summary()

    def _click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify_element(event.x, event.y).endswith('indicator'): return
        self.tree.focus(iid); self.tree.selection_set(iid); self.toggle(iid)
        return 'break'

    def _space(self, event):
        self.toggle(self.tree.focus()); return 'break'

    def update_summary(self, *_):
        if self._loading or not hasattr(self, 'summary'): return
        try:
            options = self.current_options()
            text = self.describe(self.app.query.get(), options)
        except ValueError as error: text = str(error)
        self.summary.configure(state='normal'); self.summary.delete('1.0', 'end')
        self.summary.insert('1.0', text); self.summary.configure(state='disabled')

    def describe(self, query, options):
        labels = {field: {value_key(value): label for iid, kind, value, label, icon, parent in self.entries if kind == field}
                  for field in FILTER_FIELDS}
        parts = []
        where = [self.tr('Nom')] if options.get('name', True) else []
        if options.get('comment'): where.append(self.tr('Commentaires'))
        if query: parts.append(f'{self.tr("Chercher")} « {query} » — {", ".join(where)}.')
        for field, title in (('categories', 'Catégories'), ('properties', 'Tags'), ('continents', 'Continents'), ('regions', 'Régions')):
            values = options.get(field)
            if values is not None:
                names = [labels[field].get(value_key(value), str(value) if field != 'regions' else self.tr('Région enregistrée')) for value in values]
                parts.append(self.tr(title) + ' : ' + (', '.join(names) or self.tr('Aucune')))
        if options.get('minimum') is not None or options.get('maximum') is not None:
            parts.append(self.tr('Niveau [min/max]') + f" : {options.get('minimum') if options.get('minimum') is not None else '…'} / {options.get('maximum') if options.get('maximum') is not None else '…'}")
        if options.get('local_only'): parts.append(self.tr('Ajouts Locaux'))
        if options.get('group') is not None: parts.append(f"{self.tr('Section')} : {options['group']}")
        return '\n'.join(parts) or self.tr('Aucune recherche définie')

    def presets(self):
        raw = self.app.preferences.get('search_presets', [])
        valid = []
        for item in raw[:20] if isinstance(raw, list) else []:
            if not isinstance(item, dict) or not isinstance(item.get('query'), str) or not isinstance(item.get('options'), dict): continue
            try: item = dict(item, options=saved_options(item['options']))
            except (TypeError, ValueError): continue
            valid.append(item)
        return valid

    def remember(self, query, options):
        if not query and not has_filter(options):
            return
        item = dict(self.identity(), query=query, options=saved_options(options))
        previous = [preset for preset in self.presets() if value_key(preset) != value_key(item)]
        self.app.preferences['search_presets'] = [item] + previous[:19]

    def render_history(self):
        identity = self.identity()
        self.visible_presets = [item for item in self.presets() if all(item.get(key, value) == value for key, value in identity.items())]
        for query in getattr(self.app, 'search_history', []):
            if isinstance(query, str) and query and not any(item['query'] == query for item in self.visible_presets):
                self.visible_presets.append(dict(query=query, options={}))
        self.visible_presets = self.visible_presets[:20]
        self.history.delete(*self.history.get_children())
        icon = getattr(self.app, 'toolbar_icons', {}).get(19, '')
        for index, item in enumerate(self.visible_presets):
            text = self.describe(item['query'], item['options']).replace('\n', ' · ')
            self.history.insert('', 'end', iid=str(index), text=text, image=icon)

    def recall(self, index):
        if not 0 <= index < len(self.visible_presets): return
        item = self.visible_presets[index]
        self.load_options(item['options'])
        self.current_zone.set(False); self.current_check.grid_remove()
        self.app.query.set(item['query']); self.filter_text.set('')
        self.render_tree()
        for field in FILTER_FIELDS:
            if self.criteria[field]: self.tree.item(self.roots[field], open=True)
        self.update_summary()

    def _recall_selected(self, event):
        selected = self.history.selection()
        if selected: self.recall(int(selected[0]))

    def reset(self):
        self.app.query.set(''); self.load_options({}); self.current_zone.set(False)
        self.current_check.grid_remove(); self.filter_text.set(''); self.render_tree(); self.update_summary()

    def set_expanded(self, expanded):
        self.expanded = expanded
        for root in self.roots.values(): self.tree.item(root, open=expanded)
        self.geometry(f'{max(self.winfo_width(), 540)}x{629 if expanded else 350}')

    def run(self):
        try:
            if self.identity() != self._identity: raise ValueError(self.tr('Les données ont changé. Rouvrez la recherche.'))
            if not self.names.get() and not self.comments.get(): raise ValueError(self.tr('Sélectionner Nom ou Commentaires.'))
            options = self.current_options()
            query = self.app.query.get()
            if not query.strip() and not has_filter(options):
                raise ValueError(self.tr('Saisir un nom ou un texte à rechercher.'))
        except ValueError as error:
            messagebox.showerror(self.tr('Recherche'), str(error), parent=self); return False
        self.app.search_options = options
        self.remember(query, options)
        history = [value for value in getattr(self.app, 'search_history', []) if isinstance(value, str) and value != query]
        self.app.search_history = [query] + history[:19]
        if callable(getattr(self.app, 'save_preferences', None)): self.app.save_preferences()
        self.app.search(); self.destroy(); return True

    def _enter(self, event):
        self.run(); return 'break'

    def _escape(self, event):
        self.destroy(); return 'break'

    def _focus_entry(self):
        self._focus_after = None
        self.entry.focus_set()

    def destroy(self):
        if self._focus_after is not None:
            self.after_cancel(self._focus_after); self._focus_after = None
        for variable, trace in self._traces:
            try: variable.trace_remove('write', trace)
            except tk.TclError: pass
        self._traces.clear()
        super().destroy()
