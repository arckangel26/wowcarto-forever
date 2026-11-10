import tempfile
import unittest
from pathlib import Path

from tools.forever_installation import identify


class InstallationIdentificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.product = self.root / '_forever_'
        self.product.mkdir()
        (self.root / 'Data' / 'data').mkdir(parents=True)
        self.exe = self.product / 'Wow.exe'
        self.exe.write_bytes(b'fixture')
        (self.product / '.flavor.info').write_text('Product Flavor!STRING:0\nwowf\n')
        self.build = self.root / '.build.info'
        self.build.write_text('Product!STRING:0|Active!DEC:1|Version!STRING:0\nwowf|1|1.60.1.70862\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_identifies_metadata_without_claiming_readability(self):
        result = identify(self.exe)
        self.assertEqual(result['version'], '1.60.1.70862')
        self.assertFalse(result['storage_read_verified'])

    def test_rejects_other_product_and_ambiguous_build(self):
        (self.product / '.flavor.info').write_text('Product Flavor!STRING:0\nwow\n')
        with self.assertRaises(ValueError):
            identify(self.exe)
        (self.product / '.flavor.info').write_text('Product Flavor!STRING:0\nwowf\n')
        self.build.write_text('Product|Active|Version\nwowf|1|1.60.1.70862\nwowf|1|1.60.1.70755\n')
        with self.assertRaises(ValueError):
            identify(self.exe)

    def test_refuses_wrong_executable(self):
        other = self.product / 'Other.exe'
        other.write_bytes(b'fixture')
        with self.assertRaises(ValueError):
            identify(other)
