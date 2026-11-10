"""Convert a locally extracted terrain into a checked SD or HD map pack."""
from pathlib import Path
import json
import re

from PIL import Image
from tools.map_packs import FORMAT, load_pack, sha256


def create(source, destination, quality, *, progress=None):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Source et destination doivent être distinctes.')
    if quality not in ('SD', 'HD'):
        raise ValueError('Qualité inconnue.')
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('product') != 'wowf' or not manifest.get('offline') or not re.fullmatch(
            r'\d+\.\d+\.\d+\.\d+', manifest.get('build', '')):
        raise ValueError('Manifeste Forever invalide.')
    items = manifest.get('items')
    if not isinstance(items, list) or manifest.get('ok') != sum(not item.get('error') for item in items):
        raise ValueError('Inventaire de textures incohérent.')
    destination.mkdir(parents=True, exist_ok=False)
    rows, seen = [], set()
    for index, item in enumerate(items, 1):
        if item.get('error'):
            continue
        ident = item.get('id')
        match = re.fullmatch(r'world/minimaps/(azeroth|kalimdor)/(map\d+_\d+)\.blp', item.get('name', ''), re.I)
        if type(ident) is not int or ident < 1 or not match or (match[1].casefold(), match[2].casefold()) in seen:
            raise ValueError('Texture ou identifiant invalide.')
        seen.add((match[1].casefold(), match[2].casefold()))
        image_path = source / f'{ident}.blp'
        if image_path.is_symlink() or image_path.stat().st_size != item.get('bytes') or sha256(image_path) != item.get('sha256'):
            raise ValueError('Texture source modifiée : ' + str(ident))
        with Image.open(image_path) as image:
            if image.width * image.height > 16777216:
                raise ValueError('Texture trop grande.')
            image.load()
            image = image.convert('RGB')
            if quality == 'SD':
                image.thumbnail((256, 256), Image.Resampling.LANCZOS)
            filename = f'{ident}.png'
            target = destination / filename
            image.save(target, format='PNG')
            width, height = image.size
        asset = {'path': filename, 'bytes': target.stat().st_size, 'sha256': sha256(target),
                 'width': width, 'height': height}
        rows.append({'id': match[1].lower() + '-' + match[2].lower(), 'title': match[2],
                     'group': match[1].title(), 'standard': asset, 'high': None})
        if progress:
            progress(index, len(items))
    if not rows:
        raise ValueError('Aucune carte disponible.')
    pack = {'format': FORMAT, 'id': 'wow-forever-terrain', 'title': 'WoW Forever — terrain ' + quality,
            'mode': 'Modern', 'version': 'WoW Forever ' + manifest['build'],
            'provenance': 'Textures lues localement depuis le jeu de l’utilisateur.',
            'limitations': 'Disponibilité et coordonnées à vérifier pour cette version.',
            'maps': rows}
    with (destination / 'pack.json').open('x', encoding='utf-8') as stream:
        json.dump(pack, stream, ensure_ascii=False, indent=2)
    load_pack(destination / 'pack.json', verify=True)
    return pack
