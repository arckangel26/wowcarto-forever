import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from tools.map_packs import FORMAT, sha256
from tools.prepare_forever_local import prepare


class PrepareLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.terrain = self.root / 'terrain'
        self.terrain.mkdir()
        image = self.terrain / 'tile.png'
        Image.new('RGB', (8, 8), 'red').save(image)
        asset = {'path': image.name, 'bytes': image.stat().st_size,
                 'sha256': sha256(image), 'width': 8, 'height': 8}
        pack = {'format': FORMAT, 'id': 'test', 'title': 'Test', 'mode': 'Modern',
                'provenance': 'Fixture', 'version': 'Test', 'limitations': 'Fixture',
                'maps': [{'id': 'azeroth-map1_1', 'title': 'map1_1', 'group': 'Azeroth',
                          'standard': asset, 'high': None}]}
        (self.terrain / 'pack.json').write_text(json.dumps(pack), encoding='utf-8')
        self.database = self.root / 'databases'
        for lang in ('Francais', 'US'):
            path = self.database / lang / 'master.loc'
            path.parent.mkdir(parents=True)
            path.write_bytes(lang.encode('ascii'))

    def tearDown(self):
        self.temp.cleanup()

    @patch('tools.prepare_forever_local.load_database')
    def test_private_copy_preserves_sources_and_refuses_overwrite(self, load):
        source = self.database / 'Francais' / 'master.loc'
        before = sha256(source)
        dest = self.root / 'prepared'
        catalog = prepare(dest, self.terrain, self.database)
        self.assertEqual(set(catalog['sets'][0]['databases']), {'Francais', 'US'})
        self.assertEqual(sha256(source), before)
        self.assertEqual(sha256(dest / 'databases' / 'Francais' / 'master.loc'), before)
        self.assertEqual(load.call_count, 2)
        with self.assertRaises(FileExistsError):
            prepare(dest, self.terrain, self.database)
        with self.assertRaises(ValueError):
            prepare(self.database / 'nested', self.terrain, self.database)
