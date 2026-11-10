"""Extract local terrain textures with a read-only CASC backend."""
import hashlib
import json
from pathlib import Path
import re

from tools.forever_casc import ForeverCasc
from tools.forever_installation import identify

NAME = re.compile(r'world/minimaps/(azeroth|kalimdor)/map\d+_\d+\.blp\Z', re.I)


def candidates(listfile):
    result, ids, names = [], set(), set()
    with Path(listfile).open(encoding='utf-8-sig') as stream:
        for line in stream:
            ident, separator, name = line.strip().partition(';')
            if not separator or not ident.isascii() or not ident.isdigit() or not NAME.fullmatch(name):
                continue
            number = int(ident)
            if not 1 <= number <= 0xffffffff or number in ids or name.casefold() in names:
                raise ValueError('Liste de textures invalide ou dupliquée.')
            ids.add(number)
            names.add(name.casefold())
            result.append((number, name))
    if not result:
        raise ValueError('Aucune texture de terrain dans la liste.')
    return result


def extract(executable, listfile, destination, library, *, progress=None, reader=ForeverCasc):
    installation = identify(executable)
    root = installation['root'].resolve()
    destination = Path(destination).resolve()
    if destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('La destination doit être distincte du jeu.')
    rows = candidates(listfile)
    destination.mkdir(parents=True, exist_ok=False)
    items = []
    with reader(library, installation['data']) as store:
        for index, (ident, name) in enumerate(rows, 1):
            try:
                data = store.read(ident)
            except FileNotFoundError as error:
                items.append({'id': ident, 'name': name, 'error': str(error)})
            else:
                (destination / f'{ident}.blp').write_bytes(data)
                items.append({'id': ident, 'name': name, 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest()})
            if progress:
                progress(index, len(rows))
    ok = sum(not item.get('error') for item in items)
    if not ok:
        raise ValueError('Aucune texture lisible dans le stockage local.')
    manifest = {'product': 'wowf', 'build': installation['version'], 'offline': True,
                'candidates': len(items), 'ok': ok, 'items': items}
    with (destination / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return manifest
