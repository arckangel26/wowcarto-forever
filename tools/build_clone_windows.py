"""Build the integrated Windows client from a frozen source/dependency manifest.

No game resources are included by default. --local-data is for local private use.
Existing destinations are refused; no previous build or profile is removed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import zipfile

from tools.map_packs import load_pack, local_file, sha256

ROOT = Path(__file__).resolve().parents[1]


def application_version():
    """Read the declared version without starting or importing the UI application."""
    tree = ast.parse((ROOT / 'tools/clone_app.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'VERSION'
                                               for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str): return value
    raise ValueError('Version littérale VERSION absente de tools/clone_app.py.')


VERSION = application_version()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def windows_version(version):
    """Keep application, Windows file metadata and installer versions consistent."""
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:[-+][A-Za-z0-9.-]+)?', version)
    if not match:
        raise ValueError('Version Windows invalide : ' + version)
    parts = tuple(int(value or 0) for value in match.groups())
    if any(value > 65535 for value in parts):
        raise ValueError('Composante de version Windows supérieure à 65535.')
    numeric = '.'.join(str(value) for value in parts[:4 if match[4] else 3])
    return numeric, parts


def windows_version_resource(version):
    _, parts = windows_version(version)
    strings = [('CompanyName', 'WoWCarto Forever'), ('FileDescription', 'WoWCarto Forever'),
               ('FileVersion', version), ('InternalName', 'WoWCartoForever-Client'),
               ('OriginalFilename', 'WoWCartoForever-Client.exe'),
               ('ProductName', 'WoWCarto Forever'), ('ProductVersion', version)]
    children = ',\n'.join('    StringStruct(' + repr(key) + ', ' + repr(value) + ')' for key, value in strings)
    return (f'VSVersionInfo(ffi=FixedFileInfo(filevers={parts!r}, prodvers={parts!r}, '
            'mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n'
            'kids=[StringFileInfo([StringTable("040C04B0", [\n' + children +
            '\n])]), VarFileInfo([VarStruct("Translation", [1036, 1200])])])\n')


def selected_icon(path, *, local_data):
    """Use the existing original icon only for explicitly private resource builds."""
    if path is None and local_data:
        candidate = ROOT / 'outputs/branding-original-20261105/reproduced-120.ico'
        if candidate.is_file(): path = candidate
    if path is None:
        return None
    from PIL import Image
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError('Icône Windows absente ou trop volumineuse.')
    with Image.open(path) as image:
        if image.format != 'ICO': raise ValueError('L’icône doit être un fichier ICO valide.')
        image.load()
    return path


def build(destination, *, local_data=None, iscc=None, verified_data=None, app_icon=None):
    destination = Path(destination).resolve()
    if destination.exists(): raise FileExistsError('Utiliser un nouveau dossier de construction : ' + str(destination))
    dependencies = {name: importlib.metadata.version(name) for name in ('Pillow', 'pyinstaller', 'pefile')}
    expected = {'Pillow': '12.3.0', 'pyinstaller': '6.16.0', 'pefile': '2023.2.7'}
    if dependencies != expected:
        raise ValueError('Utiliser requirements-client-windows.txt dans un environnement isolé : ' + str(dependencies))
    if platform.system() != 'Windows': raise ValueError('Construction Windows native requise.')
    numeric_version, _ = windows_version(VERSION)
    app_icon = selected_icon(app_icon, local_data=local_data)
    data_manifest = {}
    data_validation = {'method': 'complete image decode and source hashes'}
    if local_data:
        local_data = Path(local_data).resolve()
        catalog = json.loads((local_data / 'catalog.json').read_text(encoding='utf-8'))
        if catalog.get('format') != 'wcf-clone-catalog-v1': raise ValueError('Catalogue invalide.')
        for path in sorted(local_data.rglob('*')):
            if path.is_symlink(): raise ValueError('Lien refusé dans les ressources : ' + str(path))
            if path.is_file():
                relative = path.relative_to(local_data)
                if relative.parts[0] not in ('catalog.json', 'legacy-validation.json', 'databases', 'packs', 'minimaps', 'interface-originale', 'translations'):
                    raise ValueError('Fichier non prévu dans les ressources : ' + str(relative))
                data_manifest[relative.as_posix()] = sha256(path)
        if verified_data:
            previous = json.loads(Path(verified_data).read_text(encoding='utf-8'))
            if previous.get('local_private_resources') is not True or previous.get('data_sha256') != data_manifest:
                raise ValueError('Les ressources diffèrent de la construction vérifiée ; refaire une validation complète.')
            data_validation = dict(method='SHA-256 identical to previously decoded resources',
                                   previous_manifest_sha256=sha256(verified_data))
        for spec in ([] if verified_data else catalog['sets']):
            for database in spec.get('databases', {}).values():
                if sha256(local_file(local_data, database['path'])) != database['sha256']:
                    raise ValueError('Empreinte de base invalide.')
            for name in set(spec.get('packs', []) + [spec[key] for key in ('terrain_pack', 'legacy_pack') if key in spec]):
                load_pack(local_file(local_data, name), verify=True)
    destination.mkdir(parents=True)
    build_assets = destination / 'build-assets'
    build_assets.mkdir()
    version_file = build_assets / 'windows-version.txt'
    version_file.write_text(windows_version_resource(VERSION), encoding='utf-8')
    assets = {'build-assets/windows-version.txt': version_file}
    if app_icon:
        icon_copy = build_assets / 'application.ico'
        shutil.copyfile(app_icon, icon_copy)
        assets['build-assets/application.ico'] = icon_copy
    sources = sorted(set([*ROOT.glob('tools/**/*.py'), *ROOT.glob('tests/**/*.py'), *ROOT.glob('assets/first-run/*'), ROOT / 'tools/wowcarto_client.iss',
                          ROOT / 'requirements-client-windows.txt', ROOT / 'docs/CLIENT_WINDOWS.md']))
    source_hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources}
    source_zip = destination / 'sources-client.zip'
    with zipfile.ZipFile(source_zip, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sources: archive.write(path, path.relative_to(ROOT).as_posix())
        for name, path in assets.items(): archive.write(path, name)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed', '--noupx',
               '--name', 'WoWCartoForever-Client', '--paths', str(ROOT), '--distpath', str(destination),
               '--workpath', str(destination / 'build'), '--specpath', str(destination / 'build'),
               '--version-file', str(version_file),
               '--add-data', str(ROOT / 'assets/first-run') + ';first-run']
    if app_icon: command += ['--icon', str(icon_copy)]
    command.append(str(ROOT / 'tools/clone_app.py'))
    subprocess.run(command, check=True, cwd=ROOT)
    if any(sha256(ROOT / name) != digest for name, digest in source_hashes.items()):
        raise ValueError('Les sources ont changé pendant la construction ; conserver ce dossier puis reconstruire.')
    app = destination / 'WoWCartoForever-Client'
    if local_data: shutil.copytree(local_data, app / 'data')
    shutil.copyfile(ROOT / 'docs/CLIENT_WINDOWS.md', app / 'LIRE-MOI.md')
    shutil.copyfile(source_zip, app / source_zip.name)
    if app_icon: shutil.copyfile(icon_copy, app / 'application.ico')
    manifest = dict(version=VERSION, windows_numeric_version=numeric_version,
        package_edition='private-with-local-resources' if local_data else 'application-without-game-resources',
        python=sys.version, platform=platform.platform(), dependencies=dependencies,
        head=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
        git_status=git('status', '--short'), source_sha256=source_hashes, sources_zip_sha256=sha256(source_zip),
        data_sha256=data_manifest, data_validation=data_validation,
        build_assets_sha256={name: sha256(path) for name, path in assets.items()},
        application_icon_sha256=sha256(icon_copy) if app_icon else None,
        original_interface_resources=True,
        third_party_redistribution_rights='unverified',
        local_private_resources=bool(local_data), build_command=command,
        exe_sha256=sha256(app / 'WoWCartoForever-Client.exe'))
    (app / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if iscc:
        installer_command = [str(Path(iscc).resolve()), '/DBuildRoot=' + str(destination),
                             '/DProductVersion=' + VERSION, '/DProductNumericVersion=' + numeric_version]
        if local_data:
            installer_command.append('/DIncludeLocalData=1')
        if app_icon: installer_command += ['/DAppIcon=' + str(icon_copy)]
        installer_command.append(str(ROOT / 'tools/wowcarto_client.iss'))
        subprocess.run(installer_command, check=True)
        manifest['installer_command'] = installer_command
        manifest['installer_sha256'] = sha256(destination / 'installer/WoWCartoForever-Setup.exe')
    (destination / 'delivery.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(client=str(app / 'WoWCartoForever-Client.exe'), sha256=manifest['exe_sha256'],
                         installer_sha256=manifest.get('installer_sha256')), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--local-data', type=Path, help='Ressources privées pour cette machine ; ne pas publier le paquet.')
    parser.add_argument('--iscc', type=Path)
    parser.add_argument('--app-icon', type=Path, help='Icône ICO existante à intégrer ; origine et droits à vérifier pour toute redistribution.')
    parser.add_argument('--verified-data', type=Path,
                        help='delivery.json d’une construction locale vérifiée ; réutilisation seulement si toutes les empreintes sont identiques.')
    args = parser.parse_args()
    if args.verified_data and not args.local_data:
        parser.error('--verified-data nécessite --local-data')
    build(args.destination, local_data=args.local_data, iscc=args.iscc, verified_data=args.verified_data, app_icon=args.app_icon)


if __name__ == '__main__': main()
