import math
import struct
import unittest

from tools.clone_paths import MAX_PATH_POINTS, decode_native_path


class NativePathTests(unittest.TestCase):
    def test_original_bandit_vector_fixture_has_tile_local_origin_and_signed_y_deltas(self):
        # FR source f1838d49..., native annotation34020 on tile1100.
        row = dict(links='V_0091DDD7549F01D4013F000004E6FC4502A2FB64FB3F0071FB2D043EFF7C')
        tile = dict(x=-1023.984375, y=-546.875)
        path = decode_native_path(row, tile)
        self.assertEqual(path.kind, 'V')
        self.assertEqual(path.points[0], (-802.14453125, -462.25390625))
        self.assertEqual(path.points[1], (-800.31640625, -463.5))
        self.assertEqual(path.points[2], (-800.31640625, -468.3984375))
        self.assertEqual(len(path.points), 7)
        self.assertFalse(path.closed)
        self.assertEqual(path.opacity, 255)
        self.assertEqual(path.raw_options, '0091')

    def test_vector_may_cross_tile_edges_without_wrapping_unsigned_coordinates(self):
        body = struct.pack('>HHhhhh', 65500, 5, 100, 100, -200, -200).hex()
        row = dict(links='V_1031' + body)
        tile = dict(x=0, y=0)
        path = decode_native_path(row, tile)
        self.assertEqual(path.points[1], (65600 / 256, -95 / 256))
        self.assertEqual(path.points[2], (65400 / 256, 105 / 256))
        self.assertTrue(path.always_visible)
        self.assertEqual(path.opacity, 0x88)
        self.assertEqual(row['links'], 'V_1031' + body)
        self.assertEqual(tile, dict(x=0, y=0))

    def test_surface_uses_global_origin_and_existing_marker_bounds_check(self):
        body = struct.pack('>iihhhhhh', -2560, -5120, 512, 0, 0, -512, -512, 0).hex()
        row = dict(links='S_' + body, wx=-9, wy=-19)
        path = decode_native_path(row)
        self.assertEqual(path.points, ((-10, -20), (-8, -20), (-8, -18), (-10, -18)))
        self.assertTrue(path.closed)
        self.assertEqual((path.opacity, path.fill_opacity), (0xDD, 0x33))
        self.assertIsNone(decode_native_path(dict(row, wx=50)))

    def test_malformed_unsupported_and_unbounded_commands_are_ignored(self):
        good = 'V_00910000000000010001'
        for encoded in ('', 'B_0', 'I_' + '0' * 32, 'M_' + '0' * 32,
                        'V_0091', good[:-1], good + 'G', good.replace('0001', '00 1'),
                        good.replace('0091', '0A91'), 'V_0091' + '0' * (8 * (MAX_PATH_POINTS + 1))):
            with self.subTest(encoded=encoded[:24]):
                self.assertIsNone(decode_native_path(dict(links=encoded), dict(x=0, y=0)))
        self.assertIsNone(decode_native_path(dict(links=good)))
        for bad in (math.inf, math.nan, True, '0', 10 ** 20):
            self.assertIsNone(decode_native_path(dict(links=good), dict(x=bad, y=0)))


if __name__ == '__main__':
    unittest.main()
