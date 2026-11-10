"""Download the existing 1.20 reference snapshot and validate its native bases."""
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

from tools.native_database import load_database

BASE = 'https://arckangel.pages-perso.free.fr/wowcarto/reference-20261105/'
ARCHIVE_HASH = '1729d40ff8388d19b1b1f24dd88354b9ff3881f7d012d6366eb00ab5e6e9c303'
SQLITE_HASH = 'ae338ba0dc265cc37a9e1fa47a4e732a1618100767942de21345cd59f5f19d8f'
ARCHIVE_SIZE = 26071673
SQLITE_SIZE = 110776320
SOURCE_HASHES = {'Francais': 'f1838d4946221d610fb7f54241bb574670dadb3da4b1bf1398821b640b7bb6b5',
                 'US': '58ae7d6ffd4f3e6a16ef27dc696b2f9c754a1752a1ae774f30ccf7d02637761e'}


def _fetch(url, limit, opener):
    request = Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'WoWCartoForever/0.9'})
    with opener(request, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError('Redirection de téléchargement inattendue.')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Téléchargement trop volumineux.')
    return data


def download(destination, *, opener=urlopen, progress=None):
    destination = Path(destination).resolve()
    manifest = json.loads(_fetch(BASE + 'manifest.json', 64 * 1024, opener))
    spec = manifest.get('download', {})
    if (manifest.get('format') != 'wcf-public-reference-v1' or
            spec.get('file') != 'reference-120.sqlite3.gz' or spec.get('compression') != 'gzip' or
            spec.get('sha256') != ARCHIVE_HASH or spec.get('uncompressed_sha256') != SQLITE_HASH or
            spec.get('bytes') != ARCHIVE_SIZE or spec.get('uncompressed_bytes') != SQLITE_SIZE):
        raise ValueError('Manifeste de base non reconnu.')
    if progress:
        progress('Téléchargement de la base 1.20…')
    archive = _fetch(BASE + spec['file'], spec['bytes'], opener)
    if len(archive) != spec['bytes'] or hashlib.sha256(archive).hexdigest() != ARCHIVE_HASH:
        raise ValueError('Téléchargement de la base incomplet ou modifié.')
    destination.mkdir(parents=True, exist_ok=False)
    sqlite_path = destination / 'reference-120.sqlite3'
    digest = hashlib.sha256()
    count = 0
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as source, sqlite_path.open('xb') as output:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            if count > spec['uncompressed_bytes']:
                raise ValueError('Base décompressée trop volumineuse.')
            digest.update(block)
            output.write(block)
    if count != spec['uncompressed_bytes'] or digest.hexdigest() != SQLITE_HASH:
        raise ValueError('Empreinte de la base décompressée invalide.')
    if progress:
        progress('Vérification des bases française et anglaise…')
    with closing(sqlite3.connect(sqlite_path.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Intégrité SQLite incorrecte.')
        if db.execute("SELECT value FROM metadata WHERE key='format'").fetchone() != ('wcf-original-reference-sqlite-v1',):
            raise ValueError('Format de base inconnu.')
        rows = db.execute('SELECT locale,sha256,bytes,original_blob FROM sources').fetchall()
    if len(rows) != 2 or {row[0] for row in rows} != set(SOURCE_HASHES):
        raise ValueError('Langues de la base inattendues.')
    for locale, expected, size, blob in rows:
        if expected != SOURCE_HASHES[locale] or len(blob) != size or hashlib.sha256(blob).hexdigest() != expected:
            raise ValueError('Base native invalide : ' + locale)
        target = destination / locale / 'master.loc'
        target.parent.mkdir()
        with target.open('xb') as stream:
            stream.write(blob)
        load_database(target, expected_version=1200)
    return {'database_root': destination, 'sources': dict(SOURCE_HASHES)}
