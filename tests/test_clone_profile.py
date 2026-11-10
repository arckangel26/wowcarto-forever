import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.clone_profile import backup_profile, restore_profile
from tools.clone_store import Store, ConflictError


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root / 'a.sqlite3'); self.addCleanup(self.store.close)
        self.other = Store(self.root / 'b.sqlite3'); self.addCleanup(self.other.close)
        self.note = self.store.add_note(dict(name='Essai', map_id=17, x=123, y=456))
        self.store.update_note(self.note, dict(name='Modifiée'))

    def test_backup_restore_preserves_history_preferences_and_is_idempotent(self):
        backup = self.root / 'profile.wcfbackup'
        prefs = {'interface': 'Modern', 'session': {'categories': [18, 37]}}
        result = backup_profile(self.store, prefs, backup)
        self.assertEqual(result['notes'], 1)
        first = restore_profile(self.other, backup)
        self.assertEqual(first['added'], 1); self.assertEqual(first['preferences'], prefs)
        self.assertEqual(self.other.get_note(self.note), self.store.get_note(self.note))
        self.assertEqual(self.other.history(self.note), self.store.history(self.note))
        self.assertEqual(restore_profile(self.other, backup)['skipped'], 1)

    def test_tampering_and_path_entries_never_modify_local_notes(self):
        backup = self.root / 'profile.wcfbackup'; backup_profile(self.store, {}, backup)
        with zipfile.ZipFile(backup) as archive: parts = {n: archive.read(n) for n in archive.namelist()}
        parts['annotations.json'] = parts['annotations.json'].replace(b'Modifi', b'Abimee')
        bad = self.root / 'bad.wcfbackup'
        with zipfile.ZipFile(bad, 'w') as archive:
            for name, raw in parts.items(): archive.writestr(name, raw)
        with self.assertRaises(ValueError): restore_profile(self.other, bad)
        self.assertEqual(self.other.notes(), [])
        with zipfile.ZipFile(bad, 'w') as archive: archive.writestr('../escaped.json', '{}')
        with self.assertRaises(ValueError): restore_profile(self.other, bad)
        self.assertFalse((self.root.parent / 'escaped.json').exists())

    def test_conflict_retains_current_note_and_existing_backup_is_not_overwritten(self):
        backup = self.root / 'profile.wcfbackup'; backup_profile(self.store, {}, backup)
        original = backup.read_bytes()
        with self.assertRaises(FileExistsError): backup_profile(self.store, {}, backup)
        self.assertEqual(backup.read_bytes(), original)
        restore_profile(self.other, backup)
        self.other.update_note(self.note, dict(name='À conserver'))
        with self.assertRaises(ConflictError): restore_profile(self.other, backup)
        self.assertEqual(self.other.get_note(self.note)['name'], 'À conserver')


if __name__ == '__main__': unittest.main()
