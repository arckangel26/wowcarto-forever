"""Local annotation editor; source and coordinates are never changed by the form."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


def local_fields(row):
    """Copy only editable/local fields while retaining location and opaque flags."""
    flags = row.get('flags', '')
    if not isinstance(flags, str):
        flags = json.dumps(flags, ensure_ascii=False, separators=(',', ':'))
    tags = row.get('tags')
    if not isinstance(tags, str):
        tags = '; '.join(row.get('property_names', []))
    return dict(name=row.get('name', ''), comment=row.get('comment', ''),
                category=row.get('category', 37), map_id=row['map_id'], x=row['x'], y=row['y'],
                min_level=row.get('min_level', 0), max_level=row.get('max_level', 0),
                tags=tags, flags=flags)


class AnnotationDialog(simpledialog.Dialog):
    """Native-style three-column editor over a safe local annotation copy.

    The general form follows the 1.20 TFORM2 layout. Both comment views edit
    the same plain text; opaque native commands, location and flags are retained.
    """
    def __init__(self, parent, initial, categories, translate, theme=None, editable_tags=True,
                 title='Annotation locale', *, category_icons=None, properties=None, player_level=5):
        self.initial = local_fields(initial)
        self.categories = categories
        self.category_icons = category_icons or {}
        self.properties = properties or {}
        self.player_level = player_level
        self.tr = translate
        self.theme = theme
        self.editable_tags = editable_tags
        self.fields = None
        self._syncing_comment = False
        super().__init__(parent, title=self.tr(title))

    def body(self, master):
        self.resizable(True, True)
        self.minsize(760, 560)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.name = tk.StringVar(value=self.initial['name'])
        self.minimum = tk.StringVar(value=str(self.initial['min_level']))
        self.maximum = tk.StringVar(value=str(self.initial['max_level']))
        self.tags = tk.StringVar(value=self.initial['tags'])
        categories = sorted(self.categories.items(), key=lambda item: item[1]['name'].casefold())
        self.category_values = [(ident, entry['name']) for ident, entry in categories]
        if not any(ident == self.initial['category'] for ident, _ in self.category_values):
            self.category_values.append((self.initial['category'], str(self.initial['category'])))
        selected = next(text for ident, text in self.category_values if ident == self.initial['category'])
        self.category = tk.StringVar(value=selected)
        style = ttk.Style(self)
        style.configure('Annotation.Treeview', background='#808080', fieldbackground='#808080',
                        foreground='white', rowheight=14)
        self.pages = ttk.Notebook(master)
        self.pages.grid(row=0, column=0, sticky='nsew')
        general = tk.Frame(self.pages, width=776, height=500)
        general.columnconfigure(1, weight=1)
        general.rowconfigure(0, weight=1)
        advanced = tk.Frame(self.pages)
        advanced.columnconfigure(0, weight=1)
        advanced.rowconfigure(0, weight=1)
        self.pages.add(general, text=self.tr('Infos Générales'))
        self.pages.add(advanced, text=self.tr('Éditeur de commentaires avancé'))
        self.advanced_page = advanced

        category_panel = tk.Frame(general, width=169, bd=1, relief='sunken')
        category_panel.grid(row=0, column=0, sticky='nsew', padx=(4, 3), pady=6)
        category_panel.grid_propagate(False)
        category_panel.columnconfigure(0, weight=1)
        category_panel.rowconfigure(0, weight=1)
        self.category_tree = ttk.Treeview(category_panel, show='tree', selectmode='browse',
                                         style='Annotation.Treeview', takefocus=True)
        self.category_tree.grid(row=0, column=0, sticky='nsew')
        category_scroll = ttk.Scrollbar(category_panel, command=self.category_tree.yview)
        category_scroll.grid(row=0, column=1, sticky='ns')
        self.category_tree.configure(yscrollcommand=category_scroll.set)
        for ident, label in self.category_values:
            self.category_tree.insert('', 'end', iid=str(ident), text=label,
                                      image=self.category_icons.get(ident, ''))
        self.category_tree.selection_set(str(self.initial['category']))
        self.category_tree.see(str(self.initial['category']))
        self.category_tree.bind('<<TreeviewSelect>>', self.category_selected)
        self.category.trace_add('write', self.category_changed)

        center = tk.Frame(general, width=401)
        center.grid(row=0, column=1, sticky='nsew', padx=3, pady=6)
        center.columnconfigure(0, weight=1)
        center.rowconfigure(3, weight=1)
        name_group = tk.LabelFrame(center, text=self.tr('Nom (pas de commentaires, uniquement le nom exact en jeu)'))
        name_group.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        name_group.columnconfigure(0, weight=1)
        self.name_entry = tk.Entry(name_group, textvariable=self.name, width=36)
        self.name_entry.grid(row=0, column=0, sticky='ew', padx=7, pady=8)
        self.preview = tk.Label(name_group, text='TEST', width=5, bd=1, relief='sunken')
        self.preview.grid(row=0, column=1, padx=(0, 7), pady=6, ipady=3)
        position_group = tk.LabelFrame(center)
        position_group.grid(row=1, column=0, sticky='ew', pady=(0, 6))
        self.category_description = tk.StringVar(value=selected)
        tk.Label(position_group, textvariable=self.category_description, anchor='w').pack(fill='x', padx=7, pady=(5, 2))
        tk.Label(position_group, text=self.tr('La position et la source de cette annotation seront conservées.'),
                 anchor='w', justify='left', wraplength=370).pack(fill='x', padx=7, pady=(0, 6))
        level_group = tk.LabelFrame(center, text=self.tr('Niveau [min/max]'))
        level_group.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        tk.Label(level_group, text=self.tr('Minimum :')).pack(side='left', padx=(7, 3), pady=7)
        self.minimum_entry = tk.Spinbox(level_group, from_=0, to=65535, textvariable=self.minimum, width=5)
        self.minimum_entry.pack(side='left', pady=7)
        tk.Label(level_group, text=self.tr('Maximum :')).pack(side='left', padx=(8, 3), pady=7)
        self.maximum_entry = tk.Spinbox(level_group, from_=0, to=65535, textvariable=self.maximum, width=5)
        self.maximum_entry.pack(side='left', pady=7)
        self.minimum.trace_add('write', self.update_preview)
        self.maximum.trace_add('write', self.update_preview)

        self.comment_pages = ttk.Notebook(center)
        self.comment_pages.grid(row=3, column=0, sticky='nsew')
        comments = tk.Frame(self.comment_pages)
        comments.rowconfigure(0, weight=1); comments.columnconfigure(0, weight=1)
        self.comment_pages.add(comments, text=self.tr('Commentaires'))
        self.comment = tk.Text(comments, width=46, height=16, wrap='word', undo=True)
        self.comment.grid(row=0, column=0, sticky='nsew', padx=(6, 0), pady=6)
        comment_scroll = ttk.Scrollbar(comments, command=self.comment.yview)
        comment_scroll.grid(row=0, column=1, sticky='ns', pady=6, padx=(0, 4))
        self.comment.configure(yscrollcommand=comment_scroll.set)
        self.comment.insert('1.0', self.initial['comment'])
        self.comment.edit_modified(False)
        wizard = tk.Frame(self.comment_pages, padx=10, pady=12)
        self.comment_pages.add(wizard, text='lvl Wizard')
        tk.Label(wizard, text=self.tr('Affecter le même niveau minimum et maximum :'),
                 wraplength=330, justify='left').pack(anchor='w')
        self.wizard_level = tk.StringVar(value=str(self.initial['min_level']))
        tk.Spinbox(wizard, from_=0, to=65535, width=7, textvariable=self.wizard_level).pack(anchor='w', pady=10)
        tk.Button(wizard, text=self.tr('Appliquer aux deux niveaux'), command=self.apply_common_level).pack(anchor='w')
        commands = tk.Frame(self.comment_pages, padx=10, pady=12)
        self.comment_pages.add(commands, text=self.tr('Commandes'))
        tk.Label(commands, text=self.tr('Les commandes historiques restent conservées dans le texte. '
                                      'Les liens entre annotations ne sont pas modifiés ici.'),
                 wraplength=330, justify='left').pack(anchor='w')
        tk.Button(commands, text=self.tr('Copier le commentaire'), command=self.copy_comment).pack(anchor='w', pady=12)

        property_panel = tk.Frame(general, width=177, bd=1, relief='sunken')
        property_panel.grid(row=0, column=2, sticky='nsew', padx=(3, 4), pady=6)
        property_panel.grid_propagate(False)
        property_panel.columnconfigure(0, weight=1)
        property_panel.rowconfigure(0, weight=1)
        self.property_tree = ttk.Treeview(property_panel, show='tree', selectmode='browse',
                                         style='Annotation.Treeview', takefocus=True)
        self.property_tree.grid(row=0, column=0, sticky='nsew')
        property_scroll = ttk.Scrollbar(property_panel, command=self.property_tree.yview)
        property_scroll.grid(row=0, column=1, sticky='ns')
        self.property_tree.configure(yscrollcommand=property_scroll.set)
        self.property_rows = {}
        pending = list(self.properties.items())
        while pending:
            remaining = []
            for ident, entry in pending:
                parent = str(entry.get('parent', 0)) if entry.get('parent', 0) else ''
                if parent and not self.property_tree.exists(parent):
                    remaining.append((ident, entry)); continue
                self.property_rows[str(ident)] = entry['name']
                self.property_tree.insert(parent, 'end', iid=str(ident), text=entry['name'], open=True)
            if len(remaining) == len(pending):
                # Keep disconnected source properties visible instead of dropping them.
                for ident, entry in remaining:
                    self.property_rows[str(ident)] = entry['name']
                    self.property_tree.insert('', 'end', iid=str(ident), text=entry['name'], open=True)
                break
            pending = remaining
        self.property_tree.bind('<ButtonRelease-1>', self.toggle_property)
        self.property_tree.bind('<space>', self.toggle_property)
        self.tags.trace_add('write', self.refresh_properties)
        self.refresh_properties()
        tag_row = tk.Frame(general)
        tag_row.grid(row=1, column=0, columnspan=3, sticky='ew', padx=4, pady=(0, 4))
        tk.Label(tag_row, text=self.tr('Propriétés (séparées par ;) :')).pack(side='left')
        self.tags_entry = tk.Entry(tag_row, textvariable=self.tags,
                                   state='normal' if self.editable_tags else 'readonly')
        self.tags_entry.pack(side='left', fill='x', expand=True, padx=(5, 0))

        self.advanced_comment = tk.Text(advanced, width=86, height=24, wrap='none', undo=True,
                                        font=('Consolas', 10))
        self.advanced_comment.grid(row=0, column=0, sticky='nsew', padx=(6, 0), pady=(6, 0))
        advanced_y = ttk.Scrollbar(advanced, command=self.advanced_comment.yview)
        advanced_y.grid(row=0, column=1, sticky='ns', pady=(6, 0), padx=(0, 4))
        advanced_x = ttk.Scrollbar(advanced, orient='horizontal', command=self.advanced_comment.xview)
        advanced_x.grid(row=1, column=0, sticky='ew', padx=(6, 0))
        self.advanced_comment.configure(yscrollcommand=advanced_y.set, xscrollcommand=advanced_x.set)
        self.advanced_comment.insert('1.0', self.initial['comment'])
        self.advanced_comment.edit_modified(False)
        self.comment.bind('<<Modified>>', lambda event: self.sync_comments(self.comment, self.advanced_comment))
        self.advanced_comment.bind('<<Modified>>', lambda event: self.sync_comments(self.advanced_comment, self.comment))
        tk.Label(advanced, text=self.tr('Texte intégral du commentaire ; aucune commande native n’est réécrite.'),
                 anchor='w').grid(row=2, column=0, columnspan=2, sticky='ew', padx=6, pady=6)
        self.update_preview()
        self.name_entry.selection_range(0, 'end')
        return self.name_entry

    def category_selected(self, event=None):
        selected = self.category_tree.selection()
        if selected:
            label = next(label for ident, label in self.category_values if str(ident) == selected[0])
            self.category.set(label)

    def category_changed(self, *args):
        ident = next((ident for ident, label in self.category_values if label == self.category.get()), None)
        if ident is not None:
            if self.category_tree.selection() != (str(ident),):
                self.category_tree.selection_set(str(ident))
                self.category_tree.see(str(ident))
            self.category_description.set(self.category.get())
            self.update_preview()

    def update_preview(self, *args):
        from tools.clone_map import native_marker_color
        try:
            minimum, maximum = int(self.minimum.get()), int(self.maximum.get())
            ident = next(ident for ident, label in self.category_values if label == self.category.get())
            color = native_marker_color(self.categories.get(ident, {}),
                                        dict(min_level=minimum, max_level=maximum), self.player_level)
            self.preview.configure(background=color, foreground='#202020')
        except (ValueError, StopIteration):
            pass

    def refresh_properties(self, *args):
        selected = {value.strip().casefold() for value in self.tags.get().split(';') if value.strip()}
        for iid, name in self.property_rows.items():
            self.property_tree.item(iid, text=('☑ ' if name.casefold() in selected else '☐ ') + name)

    def toggle_property(self, event=None):
        if not self.editable_tags:
            return 'break'
        if event is not None and getattr(event, 'keysym', None) != 'space':
            if 'indicator' in self.property_tree.identify_element(event.x, event.y):
                return None
            iid = self.property_tree.identify_row(event.y)
        else:
            selection = self.property_tree.selection()
            iid = selection[0] if selection else ''
        if iid not in self.property_rows:
            return 'break'
        name = self.property_rows[iid]
        values = [value.strip() for value in self.tags.get().split(';') if value.strip()]
        if any(value.casefold() == name.casefold() for value in values):
            values = [value for value in values if value.casefold() != name.casefold()]
        else:
            values.append(name)
        self.tags.set('; '.join(values))
        return 'break'

    def apply_common_level(self):
        try:
            level = int(self.wizard_level.get())
            if not 0 <= level <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror(self.tr('Annotation locale'), self.tr('La plage de niveaux est invalide.'), parent=self)
            return
        self.minimum.set(str(level)); self.maximum.set(str(level))
        self.comment_pages.select(0)

    def sync_comments(self, source, target):
        if self._syncing_comment or not source.edit_modified():
            return
        self._syncing_comment = True
        try:
            value = source.get('1.0', 'end-1c')
            if target.get('1.0', 'end-1c') != value:
                target.delete('1.0', 'end'); target.insert('1.0', value)
            source.edit_modified(False); target.edit_modified(False)
        finally:
            self._syncing_comment = False

    def copy_comment(self):
        self.clipboard_clear()
        self.clipboard_append(self.comment.get('1.0', 'end-1c'))

    def buttonbox(self):
        box = tk.Frame(self)
        self.save_button = tk.Button(box, text=self.tr('OK'), width=10, command=self.ok, default='active')
        self.save_button.pack(side='right', padx=(3, 5), pady=6)
        tk.Button(box, text=self.tr('Annuler'), width=10, command=self.cancel).pack(side='right', padx=3, pady=6)
        box.pack(fill='x')
        def save(event=None):
            self.ok(event)
            return 'break'
        self.bind('<Control-Return>', save)
        self.comment.bind('<Control-Return>', save)
        self.advanced_comment.bind('<Control-Return>', save)
        def enter(event):
            if event.widget in (self.comment, self.advanced_comment):
                return None
            self.ok(event)
            return 'break'
        self.bind('<Return>', enter)
        self.bind('<Escape>', self.cancel)
        if self.theme: self.theme()

    def validate(self):
        try:
            minimum, maximum = int(self.minimum.get()), int(self.maximum.get())
            if not 0 <= minimum <= 65535 or not 0 <= maximum <= 65535 or (minimum and maximum and minimum > maximum):
                raise ValueError(self.tr('La plage de niveaux est invalide.'))
            name = self.name.get()
            if self.pages.select() == str(self.advanced_page):
                self.sync_comments(self.advanced_comment, self.comment)
            comment = self.comment.get('1.0', 'end-1c')
            tags = self.tags.get() if self.editable_tags else self.initial['tags']
            if not name.strip() or len(name) > 200 or len(comment) > 65536 or len(tags) > 4096 or '\x00' in name+comment+tags:
                raise ValueError(self.tr('Le nom, le commentaire ou les tags sont invalides.'))
            category = next(ident for ident, label in self.category_values if label == self.category.get())
            self.fields = dict(self.initial, name=name, comment=comment, tags=tags,
                               min_level=minimum, max_level=maximum, category=category)
            return True
        except (ValueError, StopIteration):
            messagebox.showerror(self.tr('Annotation locale'), self.tr('Vérifiez le nom, les niveaux, la catégorie et les longueurs des textes.'), parent=self)
            return False

    def apply(self):
        self.result = self.fields
