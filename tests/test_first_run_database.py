import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tools import first_run_database as db


class Response(io.BytesIO):
    def __init__(self, url, data):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class FirstRunDatabaseTests(unittest.TestCase):
    def test_checks_archive_and_extracts_both_bases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'source.sqlite3'
            conn = sqlite3.connect(path)
            conn.executescript('CREATE TABLE metadata(key TEXT, value TEXT); CREATE TABLE sources(locale TEXT, sha256 TEXT, bytes INT, original_blob BLOB);')
            conn.execute('INSERT INTO metadata VALUES (?,?)', ('format', 'wcf-original-reference-sqlite-v1'))
            originals = {'Francais': b'fr fixture', 'US': b'en fixture'}
            hashes = {k: hashlib.sha256(v).hexdigest() for k, v in originals.items()}
            for lang, data in originals.items():
                conn.execute('INSERT INTO sources VALUES(?,?,?,?)', (lang, hashes[lang], len(data), data))
            conn.commit(); conn.close()
            raw = path.read_bytes()
            zipped = gzip.compress(raw)
            archive_hash = hashlib.sha256(zipped).hexdigest()
            sqlite_hash = hashlib.sha256(raw).hexdigest()
            manifest = {'format': 'wcf-public-reference-v1', 'download': {
                'file': 'reference-120.sqlite3.gz', 'compression': 'gzip', 'bytes': len(zipped),
                'uncompressed_bytes': len(raw), 'sha256': archive_hash, 'uncompressed_sha256': sqlite_hash}}
            def opener(request, timeout):
                data = json.dumps(manifest).encode() if request.full_url.endswith('manifest.json') else zipped
                return Response(request.full_url, data)
            with patch.multiple(db, ARCHIVE_HASH=archive_hash, SQLITE_HASH=sqlite_hash,
                                ARCHIVE_SIZE=len(zipped), SQLITE_SIZE=len(raw), SOURCE_HASHES=hashes), \
                 patch.object(db, 'load_database'):
                result = db.download(root / 'downloaded', opener=opener)
            self.assertEqual(result['sources'], hashes)
            self.assertEqual((root / 'downloaded' / 'Francais' / 'master.loc').read_bytes(), originals['Francais'])

    def test_rejects_unrecognised_manifest(self):
        def opener(request, timeout):
            return Response(request.full_url, b'{}')
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                db.download(Path(temp) / 'result', opener=opener)
