"""Identify a local Forever installation without starting or changing the game."""
import csv
from pathlib import Path
import re


def read_metadata(path):
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Métadonnées trop volumineuses.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = csv.reader(stream, delimiter='|')
        try:
            header = [column.split('!', 1)[0].strip().casefold() for column in next(rows)]
        except StopIteration as error:
            raise ValueError('Métadonnées vides.') from error
        if not header or any(not column for column in header) or len(set(header)) != len(header):
            raise ValueError('Colonnes de métadonnées invalides.')
        result = []
        for row in rows:
            if not any(cell.strip() for cell in row):
                continue
            if len(row) != len(header):
                raise ValueError('Métadonnées incohérentes.')
            result.append(dict(zip(header, (cell.strip() for cell in row))))
        return result


def identify(executable):
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file() or executable.name.casefold() != 'wow.exe':
        raise ValueError('Sélectionnez le fichier Wow.exe du client WoW Forever.')
    product_dir = executable.parent
    root = product_dir.parent
    flavor = read_metadata(product_dir / '.flavor.info')
    products = {row.get('product flavor', '').casefold() for row in flavor}
    if products != {'wowf'}:
        raise ValueError('Ce client ne se présente pas comme WoW Forever.')
    rows = read_metadata(root / '.build.info')
    selected = [row for row in rows if row.get('product', '').casefold() == 'wowf'
                and row.get('active') == '1']
    if len(selected) != 1 or not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', selected[0].get('version', '')):
        raise ValueError('Impossible de déterminer une version Forever active unique.')
    data = root / 'Data'
    if not (data / 'data').is_dir():
        raise ValueError('Le stockage de données du jeu est introuvable.')
    return {'executable': executable, 'root': root, 'data': data,
            'product': 'wowf', 'version': selected[0]['version'],
            'storage_read_verified': False}
