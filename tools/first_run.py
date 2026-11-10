"""First-run setup for a local Forever game and the hosted 1.20 reference."""
from functools import partial
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

from tools.first_run_database import download
from tools.forever_casc import ForeverCasc
from tools.forever_extract import extract
from tools.forever_installation import identify
from tools.forever_pack import create
from tools.prepare_forever_local import prepare


def assets_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'first-run'
    return Path(__file__).resolve().parents[1] / 'assets' / 'first-run'


def save_preferences(path, data_directory, language):
    path = Path(path)
    if path.exists():
        preferences = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(preferences, dict):
            raise ValueError('Préférences existantes illisibles ; elles ont été conservées.')
    else:
        preferences = {}
    preferences.update(data_directory=str(data_directory), map_mode='Modern',
                       database=language, consultation_only=True, welcome_seen=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     prefix='.wcf-first-run-', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(preferences, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class FirstRun:
    def __init__(self, state):
        self.state = Path(state).resolve()
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.root = tk.Tk()
        self.root.title('WoWCarto Forever — première installation')
        self.root.geometry('660x310')
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.busy = False
        self.result = None
        self.quality = tk.StringVar(value='SD')
        self.language = tk.StringVar(value='Francais')
        self.path = tk.StringVar()
        self.status = tk.StringVar(value='Sélectionnez le fichier Wow.exe de WoW Forever.')
        self.frame = ttk.Frame(self.root, padding=20)
        self.frame.pack(fill='both', expand=True)
        ttk.Label(self.frame, text='Bienvenue dans WoWCarto Forever', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        self.body = ttk.Frame(self.frame)
        self.body.pack(fill='both', expand=True, pady=(15, 6))
        self.progress = ttk.Progressbar(self.frame, maximum=100)
        self.progress.pack(fill='x')
        ttk.Label(self.frame, textvariable=self.status, wraplength=610).pack(anchor='w', pady=(5, 0))
        self.show_game()
        self.root.after(100, self.poll)

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()

    def show_game(self):
        self.clear()
        ttk.Label(self.body, text='1. Choisissez votre jeu et la qualité des cartes.').pack(anchor='w')
        line = ttk.Frame(self.body); line.pack(fill='x', pady=10)
        ttk.Entry(line, textvariable=self.path).pack(side='left', fill='x', expand=True)
        ttk.Button(line, text='Parcourir…', command=self.browse).pack(side='left', padx=(8, 0))
        choices = ttk.Frame(self.body); choices.pack(anchor='w')
        ttk.Radiobutton(choices, text='SD (256 px)', variable=self.quality, value='SD').pack(side='left')
        ttk.Radiobutton(choices, text='HD (jusqu’à 512 px)', variable=self.quality, value='HD').pack(side='left', padx=15)
        ttk.Button(self.body, text='Générer les cartes', command=self.start_maps).pack(anchor='e', pady=12)

    def browse(self):
        path = filedialog.askopenfilename(parent=self.root, title='Choisissez Wow.exe',
                                          filetypes=[('Exécutable WoW', '*.exe')])
        if path:
            self.path.set(path)

    def start_maps(self):
        try:
            info = identify(self.path.get())
            assets = assets_dir()
            for name in ('CascLib.dll', 'terrain-listfile.csv'):
                if not (assets / name).is_file():
                    raise ValueError('Composant de génération absent : ' + name)
        except (OSError, ValueError) as error:
            messagebox.showerror('Jeu introuvable', str(error), parent=self.root)
            return
        self.game = info
        self.work = tempfile.TemporaryDirectory(prefix='.wcf-first-run-', dir=self.state.parent)
        self.work_path = Path(self.work.name)
        self.clear()
        ttk.Label(self.body, text='Génération des cartes en cours…').pack(anchor='w')
        self.status.set('Lecture locale des cartes du jeu.')
        self.busy = True
        quality = self.quality.get()
        def work():
            try:
                emit = lambda label, current, total: self.events.put(('progress', label, current, total))
                raw = self.work_path / 'textures'
                extract(self.game['executable'], assets / 'terrain-listfile.csv', raw, assets / 'CascLib.dll',
                        reader=partial(ForeverCasc, wide=True),
                        progress=lambda current, total: emit('Lecture des textures', current, total))
                self.terrain = self.work_path / 'terrain'
                create(raw, self.terrain, quality,
                       progress=lambda current, total: emit('Génération des cartes', current, total))
                self.events.put(('maps_done',))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def show_language(self):
        self.clear()
        self.progress['value'] = 0
        self.status.set('Les informations seront enregistrées localement.')
        ttk.Label(self.body, text='2. Choisissez la langue de la base 1.20.').pack(anchor='w')
        ttk.Radiobutton(self.body, text='Français', variable=self.language, value='Francais').pack(anchor='w', pady=(12, 0))
        ttk.Radiobutton(self.body, text='Anglais (US)', variable=self.language, value='US').pack(anchor='w')
        ttk.Label(self.body, text='Les autres langues ne sont pas disponibles dans cette base.').pack(anchor='w', pady=10)
        ttk.Button(self.body, text='Télécharger et ouvrir', command=self.start_database).pack(anchor='e')

    def start_database(self):
        self.clear()
        ttk.Label(self.body, text='Préparation des informations locales…').pack(anchor='w')
        self.busy = True
        language = self.language.get()
        def work():
            try:
                db = download(self.work_path / 'reference', progress=lambda msg: self.events.put(('status', msg)))
                target = self.state.parent / ('data-' + uuid.uuid4().hex)
                self.events.put(('status', 'Assemblage et vérification des données locales…'))
                prepare(target, self.terrain, db['database_root'], interface_assets=assets_dir())
                save_preferences(self.state.with_name('client-preferences.json'), target, language)
                self.events.put(('complete', str(target)))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'progress':
                    self.status.set(f'{event[1]} : {event[2]} / {event[3]}')
                    self.progress['value'] = 100 * event[2] / max(1, event[3])
                elif event[0] == 'status':
                    self.status.set(event[1])
                elif event[0] == 'maps_done':
                    self.busy = False
                    self.show_language()
                elif event[0] == 'complete':
                    self.busy = False
                    self.result = Path(event[1])
                    self.root.destroy()
                    return
                elif event[0] == 'error':
                    self.busy = False
                    messagebox.showerror('Première installation', event[1], parent=self.root)
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Préparation en cours', 'Attendez la fin de l’étape en cours.', parent=self.root)
            return
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
            return self.result
        finally:
            if hasattr(self, 'work'):
                self.work.cleanup()


def run(state):
    return FirstRun(state).run()
