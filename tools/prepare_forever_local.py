"""Prepare a private local catalog from installed 1.20 bases and generated terrain."""
from pathlib import Path
import json
import shutil

from PIL import Image
from tools.map_packs import load_pack, local_file, sha256
from tools.native_database import load_database


def prepare(destination, terrain, database_root, *, interface_assets=None):
    destination = Path(destination).resolve()
    terrain = Path(terrain).resolve(strict=True)
    database_root = Path(database_root).resolve(strict=True)
    roots = [terrain, database_root]
    if interface_assets is not None:
        interface_assets = Path(interface_assets).resolve(strict=True)
        roots.append(interface_assets)
    if any(destination.is_relative_to(root) or root.is_relative_to(destination) for root in roots):
        raise ValueError('La destination doit être distincte des sources.')
    pack = load_pack(terrain / 'pack.json', verify=True)
    if pack['mode'] != 'Modern' or not pack['maps']:
        raise ValueError('Le pack ne contient pas de terrain Forever.')
    sources = {}
    for language in ('Francais', 'US'):
        path = database_root / language / 'master.loc'
        if path.is_symlink() or not path.is_file():
            raise ValueError('Base locale absente : ' + language)
        digest = sha256(path)
        load_database(path, expected_version=1200)
        if sha256(path) != digest:
            raise ValueError('Base modifiée pendant sa validation : ' + language)
        sources[language] = (path, digest)
    destination.mkdir(parents=True, exist_ok=False)
    databases = {}
    for language, (source, digest) in sources.items():
        target = destination / 'databases' / language / 'master.loc'
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        if sha256(target) != digest or sha256(source) != digest:
            raise ValueError('Base modifiée pendant sa copie : ' + language)
        databases[language] = {'path': target.relative_to(destination).as_posix(), 'sha256': digest}
    target_pack = destination / 'packs' / 'forever-terrain'
    target_pack.mkdir(parents=True)
    for row in pack['maps']:
        for kind in ('standard', 'high'):
            asset = row.get(kind)
            if asset is None:
                continue
            src = local_file(terrain, asset['path'])
            dst = target_pack.joinpath(*asset['path'].split('/'))
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile(src, dst)
                if sha256(src) != asset['sha256'] or sha256(dst) != asset['sha256']:
                    raise ValueError('Texture modifiée pendant sa copie : ' + asset['path'])
    shutil.copyfile(terrain / 'pack.json', target_pack / 'pack.json')
    load_pack(target_pack / 'pack.json', verify=True)
    if interface_assets is not None:
        target_ui = destination / 'interface-originale'
        target_ui.mkdir()
        for name in ('icon_a.bmp', 'icon_b.bmp'):
            source = interface_assets / name
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 1_000_000:
                raise ValueError('Icône locale invalide : ' + name)
            with Image.open(source) as image:
                if image.format != 'BMP' or image.height != 16 or image.width < 16 or image.width > 4096:
                    raise ValueError('Dimensions d’icône locales invalides : ' + name)
                image.load()
            digest = sha256(source)
            shutil.copyfile(source, target_ui / name)
            if sha256(source) != digest or sha256(target_ui / name) != digest:
                raise ValueError('Icône locale modifiée pendant sa copie : ' + name)
    catalog = {'format': 'wcf-clone-catalog-v1', 'sets': [
        {'id': 'reference120', 'title': 'Base 1.20 locale', 'mode': 'Référence 1.20',
         'databases': databases, 'packs': [], 'community_coordinate_system': 'wowcartographe-120'},
        {'id': 'forever-local', 'title': pack['version'].replace('WoW Forever ', 'Forever ', 1), 'mode': 'Modern',
         'terrain_pack': 'packs/forever-terrain/pack.json'}]}
    with (destination / 'catalog.json').open('x', encoding='utf-8') as stream:
        json.dump(catalog, stream, ensure_ascii=False, indent=2)
    return catalog
