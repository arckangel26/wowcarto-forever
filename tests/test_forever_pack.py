import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from tools.forever_pack import create
from tools.map_packs import load_pack, sha256


class ForeverPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        image = self.source / '123.blp'
        Image.new('RGB', (512, 512), 'red').save(image, format='PNG')
        self.manifest = {'product': 'wowf', 'build': '1.60.1.70862', 'offline': True, 'ok': 1,
                         'items': [{'id': 123, 'name': 'world/minimaps/azeroth/map1_2.blp',
                                    'bytes': image.stat().st_size, 'sha256': sha256(image)}]}
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_sd_and_hd_produce_verified_packs(self):
        for quality, size in [('SD', 256), ('HD', 512)]:
            dest = self.root / quality
            pack = create(self.source, dest, quality)
            self.assertEqual(pack['maps'][0]['standard']['width'], size)
            self.assertEqual(load_pack(dest / 'pack.json', verify=True)['version'], 'WoW Forever 1.60.1.70862')

    def test_changed_source_and_existing_destination_are_rejected(self):
        (self.source / '123.blp').write_bytes(b'altered')
        with self.assertRaises(ValueError):
            create(self.source, self.root / 'bad', 'HD')
        with self.assertRaises(FileExistsError):
            create(self.source, self.root / 'bad', 'HD')
