"""Checksummed local profile backup; restoration merges without overwriting notes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from tools.clone_store import MAX_EXPORT


FORMAT = 'wcf-profile-v1'
MAX_PROFILE = MAX_EXPORT + 2 * 1024 * 1024


def backup_profile(store, preferences, destination):
    destination = Path(destination)
    with tempfile.TemporaryDirectory(prefix='wcf-backup-') as directory:
        notes = Path(directory) / 'annotations.json'
        exported = store.export_notes(notes)
        parts = {'annotations.json': notes.read_bytes(),
                 'preferences.json': json.dumps(preferences, ensure_ascii=False,
                    default=lambda value: sorted(value) if isinstance(value, set) else str(value)).encode('utf-8')}
        if sum(map(len, parts.values())) > MAX_PROFILE:
            raise ValueError('Profil trop volumineux.')
        manifest = dict(format=FORMAT, sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in parts.items()})
        with destination.open('xb') as stream:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, raw in parts.items(): archive.writestr(name, raw)
                archive.writestr('manifest.json', json.dumps(manifest))
    return dict(notes=exported['notes'], sha256=hashlib.sha256(destination.read_bytes()).hexdigest())


def restore_profile(store, source):
    source = Path(source)
    if source.stat().st_size > MAX_PROFILE:
        raise ValueError('Profil trop volumineux.')
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if (len(entries) != 3 or {e.filename for e in entries} !=
                {'manifest.json', 'annotations.json', 'preferences.json'} or
                sum(e.file_size for e in entries) > MAX_PROFILE):
                raise ValueError('Contenu de sauvegarde invalide.')
            parts = {e.filename: archive.read(e) for e in entries}
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ValueError('Sauvegarde illisible.') from error
    manifest = json.loads(parts.pop('manifest.json'))
    if (not isinstance(manifest, dict) or manifest.get('format') != FORMAT or
        manifest.get('sha256') != {name: hashlib.sha256(raw).hexdigest() for name, raw in parts.items()}):
        raise ValueError('Empreinte de sauvegarde invalide ; aucune donnée modifiée.')
    preferences = json.loads(parts['preferences.json'])
    if not isinstance(preferences, dict):
        raise ValueError('Préférences de sauvegarde invalides.')
    with tempfile.TemporaryDirectory(prefix='wcf-restore-') as directory:
        notes = Path(directory) / 'annotations.json'
        notes.write_bytes(parts['annotations.json'])
        result = store.import_notes(notes)
    return dict(result, preferences=preferences)
