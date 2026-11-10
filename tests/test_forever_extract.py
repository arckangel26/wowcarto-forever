import json
import tempfile
import unittest
from pathlib import Path

from tools.forever_extract import candidates, extract


class FakeStore:
    def __init__(self, *_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, ident):
        if ident == 2:
            raise FileNotFoundError('absent')
        return b'fixture texture'


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        game = self.root / 'game'
        product = game / '_forever_'
        product.mkdir(parents=True)
        (game / 'Data' / 'data').mkdir(parents=True)
        self.exe = product / 'Wow.exe'
        self.exe.write_bytes(b'fixture')
        (product / '.flavor.info').write_text('Product Flavor!STRING:0\nwowf\n')
        (game / '.build.info').write_text('Product|Active|Version\nwowf|1|1.60.1.70862\n')
        self.listfile = self.root / 'list.csv'
        self.listfile.write_text('1;world/minimaps/azeroth/map1_1.blp\n2;world/minimaps/azeroth/map1_2.blp\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_extract_records_missing_without_writing_in_game(self):
        progress = []
        dest = self.root / 'extracted'
        result = extract(self.exe, self.listfile, dest, None, reader=FakeStore,
                         progress=lambda current, total: progress.append((current, total)))
        self.assertEqual((result['ok'], result['candidates']), (1, 2))
        self.assertEqual(progress[-1], (2, 2))
        self.assertEqual(json.loads((dest / 'manifest.json').read_text())['build'], '1.60.1.70862')
        self.assertEqual((dest / '1.blp').read_bytes(), b'fixture texture')
        with self.assertRaises(ValueError):
            extract(self.exe, self.listfile, self.exe.parent / 'output', None, reader=FakeStore)
        with self.assertRaises(FileExistsError):
            extract(self.exe, self.listfile, dest, None, reader=FakeStore)

    def test_duplicate_ids_fail_before_extraction(self):
        with self.listfile.open('a') as stream:
            stream.write('1;world/minimaps/kalimdor/map2_2.blp\n')
        with self.assertRaises(ValueError):
            candidates(self.listfile)
