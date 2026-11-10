"""Validate Windows metadata and resource selection without building or installing."""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

from tools.build_clone_windows import selected_icon, windows_version, windows_version_resource


class WindowsPackageTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('PyInstaller') is not None,
                         'Windows build dependency PyInstaller is not available')
    def test_version_resource_roundtrips_through_actual_pyinstaller_encoder(self):
        from PyInstaller.utils.win32 import versioninfo
        resource = eval(windows_version_resource('2.14.316-rc.1'), versioninfo.__dict__)
        self.assertEqual(resource.ffi.fileVersionMS, (2 << 16) | 14)
        self.assertEqual(resource.ffi.fileVersionLS, 316 << 16)
        self.assertEqual(resource.ffi.productVersionMS, resource.ffi.fileVersionMS)
        strings = {entry.name: entry.val for entry in resource.kids[0].kids[0].kids}
        self.assertEqual(strings['ProductVersion'], '2.14.316-rc.1')
        self.assertEqual(strings['OriginalFilename'], 'WoWCartoForever-Client.exe')
        self.assertTrue(resource.toRaw())
        self.assertEqual(windows_version('2.14.316-rc.1')[0], '2.14.316')

    def test_windows_version_rejects_invalid_or_overflowing_components(self):
        for version in ('v1.2.3', '1.2', '1.2.70000', '1.2.3 extra', '1.2.3;other'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                windows_version(version)
        self.assertEqual(windows_version('1.2.3.4'), ('1.2.3.4', (1, 2, 3, 4)))

    def test_no_data_build_does_not_implicitly_include_original_icon(self):
        self.assertIsNone(selected_icon(None, local_data=None))

    def test_explicit_invalid_icon_is_rejected_before_any_build(self):
        with tempfile.TemporaryDirectory() as directory:
            icon = Path(directory) / 'invalid.ico'
            icon.write_text('not an icon', encoding='ascii')
            with self.assertRaises((ValueError, OSError)):
                selected_icon(icon, local_data=None)


if __name__ == '__main__':
    unittest.main()
