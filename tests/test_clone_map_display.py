import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image

from tools.clone_map import MapCanvas, native_marker_color, native_zoom_visibility


class MapDisplayTests(unittest.TestCase):
    def test_elite_and_boss_have_larger_colored_fields_than_normal_mob(self):
        root = tk.Tk(); self.addCleanup(root.destroy)
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=lambda message: None)
        canvas.pack(); root.update(); canvas.scale = 2
        canvas.categories = {i: dict(native_class=1, color_rgb='#eff0de', zoom_tier=3) for i in (7, 32)}
        canvas.records = [dict(key='normal', wx=-35, wy=0, category=7, name='Normal', property_ids=[]),
                          dict(key='elite', wx=0, wy=0, category=7, name='Élite', property_ids=[16]),
                          dict(key='boss', wx=35, wy=0, category=32, name='Boss', property_ids=[])]
        canvas.draw()
        widths = [canvas.coords(item)[2] - canvas.coords(item)[0]
                  for item in canvas.find_withtag('annotation') if canvas.type(item) == 'rectangle']
        self.assertEqual(widths, [10, 14, 14])
        self.assertFalse(any(canvas.type(i) == 'oval' for i in canvas.find_all()))
    def test_native_category_visibility_at_zoom_thresholds(self):
        for pixels, icons, labels in [(199, (True, False, False), (False, False, False)),
                                      (200, (True, True, False), (True, False, False)),
                                      (399, (True, True, False), (True, False, False)),
                                      (400, (True, True, True), (True, True, False)),
                                      (599, (True, True, True), (True, True, False)),
                                      (600, (True, True, True), (True, True, True))]:
            actual = [native_zoom_visibility({'zoom_tier': tier}, pixels / 256) for tier in (1, 2, 3)]
            self.assertEqual(tuple(item[0] for item in actual), icons)
            self.assertEqual(tuple(item[1] for item in actual), labels)
    def test_native_difficulty_boundaries_and_level_intervals(self):
        category = dict(native_class=1, color_rgb='#eff0de')
        cases = [(20, 29, '#aa2515'), (20, 25, '#f82515'), (20, 23, '#fbb214'),
                 (20, 22, '#fffc1d'), (20, 18, '#fffc1d'), (20, 17, '#6be33c'),
                 (20, 14, '#6be33c'), (20, 13, '#c9d8e1'), (39, 31, '#c9d8e1'),
                 (40, 32, '#6be33c'), (40, 31, '#c9d8e1'),
                 (59, 48, '#6be33c'), (59, 47, '#c9d8e1'), (60, 51, '#c9d8e1')]
        for player, mob, expected in cases:
            with self.subTest(player=player, mob=mob):
                self.assertEqual(native_marker_color(category, dict(min_level=mob, max_level=mob), player), expected)
        self.assertEqual(native_marker_color(category, dict(min_level=10, max_level=30), 20), '#fffc1d')
        self.assertEqual(native_marker_color(category, dict(min_level=10, max_level=18), 20), '#fffc1d')
        self.assertEqual(native_marker_color(category, dict(min_level=23, max_level=30), 20), '#fbb214')
        self.assertEqual(native_marker_color(category, dict(min_level=0, max_level=0), 20), '#eff0de')
        self.assertEqual(native_marker_color(category, dict(min_level=29, max_level=29), 20, color_by_level=False), '#eff0de')
        self.assertEqual(native_marker_color(dict(native_class=2, color_rgb='#123456'),
                                            dict(min_level=29, max_level=29), 20), '#123456')

    def test_selected_mob_has_enlarged_square_without_selection_decoration(self):
        root = tk.Tk(); self.addCleanup(root.destroy)
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=lambda message: None)
        canvas.pack(); root.update()
        canvas.categories = {7: dict(native_class=1, color_rgb='#eff0de')}
        canvas.player_level = 20
        canvas.records = [dict(key='mob', wx=0, wy=0, category=7, name='Mob', min_level=25, max_level=25)]
        canvas.selected = 'mob'; canvas.draw()
        shapes = canvas.find_withtag('annotation')
        self.assertEqual([canvas.type(i) for i in shapes], ['rectangle'])
        self.assertFalse(any(canvas.type(i) == 'oval' for i in canvas.find_all()))
        self.assertFalse(any(canvas.type(i) == 'text' and canvas.itemcget(i, 'text') == 'Mob'
                             for i in canvas.find_all()))
        self.assertEqual(canvas.itemcget(shapes[0], 'fill'), '#f82515')
        x0, y0, x1, y1 = canvas.coords(shapes[0])
        self.assertEqual((x1-x0, y1-y0), (10, 10))
        canvas.scale = 3; canvas.draw()
        x0, y0, x1, y1 = canvas.coords(canvas.find_withtag('annotation')[0])
        self.assertEqual((x1-x0, y1-y0), (10, 10))
        canvas.player_level = 30; canvas.draw()
        self.assertEqual(canvas.itemcget(canvas.find_withtag('annotation')[0], 'fill'), '#6be33c')

    def test_invalid_hd_falls_back_to_checked_standard_and_category_filter_hides_hits(self):
        root = tk.Tk(); self.addCleanup(root.destroy)
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=lambda message: None)
        canvas.pack(); root.update()
        tile = dict(id='t', x=0, y=0, root='.', standard={'path': 'standard'}, high={'path': 'hd'})
        def image(root, asset):
            if asset['path'] == 'hd': raise ValueError('HD manquante')
            return Image.new('RGB', (32, 32), 'blue')
        with patch('tools.clone_map.checked_image', side_effect=image):
            self.assertEqual(canvas.asset_image(tile).size, (32, 32))
            row = dict(key='p',wx=128,wy=128,category=37,name='Personnel',source='personal')
            canvas.set_scene([tile],[row]); root.update(); canvas.draw()
            self.assertEqual(len(canvas.hits), 1)
            canvas.category_filter = {18}; canvas.draw()
            self.assertEqual(canvas.hits, [])

    def test_zoom_preserves_map_point_under_cursor_at_several_locations(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Fenêtre Tk indisponible : {error}')
        self.addCleanup(root.destroy)
        root.geometry('640x480')
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=lambda message: None)
        canvas.pack(fill='both', expand=True); root.update()
        for center in [(-1024.,-1280.),(0.,0.),(12000.,-9400.)]:
            canvas.cx,canvas.cy=center
            for x,y in [(60,60),(320,240),(590,410)]:
                for scale in (.1,.5,1.,3.,7.5):
                    before=canvas.world(x,y)
                    canvas.zoom_to(scale,x,y)
                    after=canvas.world(x,y)
                    self.assertAlmostEqual(before[0],after[0],places=8)
                    self.assertAlmostEqual(before[1],after[1],places=8)
                    px,py=canvas.screen(*after)
                    self.assertAlmostEqual(px,x,places=8)
                    self.assertAlmostEqual(py,y,places=8)

    def test_personal_annotation_is_not_hidden_by_overlapping_native_point(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Fenêtre Tk indisponible : {error}')
        self.addCleanup(root.destroy)
        root.geometry('360x300')
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=lambda message: None)
        canvas.pack(fill='both', expand=True); root.update()
        tile = dict(id='tile', x=0, y=0, width=256, height=256, root='.', standard=None, high=None)
        native = dict(key='native',wx=128,wy=128,category=1,name='Origine',source='native')
        personal = dict(key='personal',wx=128,wy=128,category=1,name='Personnel',source='personal')
        canvas.set_scene([tile],[native,personal]); root.update(); canvas.draw()
        x,y=canvas.screen(128,128)
        self.assertEqual(canvas.hit(x,y)['key'],'personal')

    def test_missing_tile_and_dense_annotations_do_not_show_diagnostic_numbers(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Fenêtre Tk indisponible : {error}')
        self.addCleanup(root.destroy)
        root.geometry('360x300')
        messages = []
        canvas = MapCanvas(root, on_select=lambda row: None, on_context=lambda *args: None,
                           on_view=lambda view: None, status=messages.append)
        canvas.pack(fill='both', expand=True)
        root.update()
        tile = dict(id='tile-123', filename='map12_34', x=0, y=0, width=256, height=256,
                    root='.', standard=None, high=None)
        records = [dict(key=str(i), wx=128, wy=128, category=1, name='Annotation') for i in range(5)]
        canvas.set_scene([tile], records)
        root.update()
        canvas.draw()
        texts = [canvas.itemcget(item, 'text') for item in canvas.find_all() if canvas.type(item) == 'text']
        self.assertEqual(texts, [])
        self.assertTrue(any('absente' in message for message in messages))


if __name__ == '__main__':
    unittest.main()
