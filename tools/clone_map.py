"""Continuous map canvas for the reconstructed client; no filename grid inference."""
from __future__ import annotations

from collections import OrderedDict
from itertools import chain
import math
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageDraw, ImageEnhance, ImageTk

from tools.map_packs import checked_image


NATIVE_DIFFICULTY_COLORS = ('#c9d8e1', '#6be33c', '#fffc1d', '#fbb214', '#f82515', '#aa2515')
MARKER_DISPLAY_SCALE = 2


def native_zoom_visibility(category, scale):
    """1.20 thresholds in rendered pixels per 256-unit tile (200, 400, 600)."""
    tier = category.get('zoom_tier', 1)
    if tier not in (1, 2, 3): tier = 1
    pixels = round(scale * 256)
    return pixels >= (0, 200, 400)[tier - 1], pixels >= (200, 400, 600)[tier - 1]


def native_marker_color(category, row, player_level, *, color_by_level=True):
    """Port of 1.20 routines 52C7FC / 4DA524 / 4DA580 (local x86 reference)."""
    fallback = category.get('color_rgb', '#eff0de')
    minimum, maximum = row.get('min_level', 0), row.get('max_level', 0)
    if not color_by_level or category.get('native_class') != 1 or not minimum:
        return fallback
    level = min(max(player_level, minimum), maximum)
    delta = level - player_level
    if delta >= 9: index = 5
    elif delta >= 5: index = 4
    elif delta >= 3: index = 3
    elif delta >= -2: index = 2
    else:
        grey = -(player_level // 10) - 5
        if player_level >= 40: grey = -(player_level // 5) - 1
        if player_level >= 60: grey = -9
        index = 1 if delta > grey else 0
    return NATIVE_DIFFICULTY_COLORS[index]


class MapCanvas(tk.Canvas):
    def __init__(self, owner, *, on_select, on_context, on_view, status, translate=lambda text: text, **kwargs):
        super().__init__(owner, background='#63859c', highlightthickness=1,
                         highlightbackground='#808080', takefocus=True, **kwargs)
        self.on_select, self.on_context, self.on_view, self.status = on_select, on_context, on_view, status
        self.translate = translate
        self.tiles, self.records, self.photos, self.hits = [], [], [], []
        self.region_markers, self.region_hits, self.region_outline = [], [], []
        self.on_region_select = None
        self.region_icon = None
        self.cache, self.icons = OrderedDict(), {}
        self.categories = {}
        self.player_level = 5
        self.marker_scale = MARKER_DISPLAY_SCALE
        self.annotations_visible = True
        self.color_by_level = True
        self.category_colors = {}
        self.category_fonts = {}
        self.paths_visible = False
        self.path_decoder = None
        self.path_cache = {}
        self.on_edit = None
        self.on_route_point = None
        self.on_route_finish = None
        self.route_editing = False
        self.personal_paths = []
        self.category_filter = None
        self.cx = self.cy = 0.
        self.scale = 1.
        self.one_to_one_scale = 4.
        self.legend, self.dim, self.high = False, False, True
        self.selected, self.dragging, self.start = None, False, None
        self.pending = None
        self.bind('<Configure>', lambda e: self.schedule())
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<Double-Button-1>', self.double_click)
        self.bind('<Button-3>', self.context)
        self.bind('<MouseWheel>', lambda e: self.zoom_to(self.scale * (1.25 if e.delta > 0 else .8), e.x, e.y))
        self.bind('<Motion>', self.hover)
        for key, delta in [('Left', (-80, 0)), ('Right', (80, 0)), ('Up', (0, -80)), ('Down', (0, 80))]:
            self.bind('<' + key + '>', lambda e, d=delta: self.move(*d))
        self.bind('<Home>', lambda e: self.fit())

    def set_scene(self, tiles, records, *, fit=True):
        self.tiles, self.records, self.selected = list(tiles), list(records), None
        self.path_cache.clear()
        if fit:
            self.fit()
        else:
            self.schedule()

    def destroy(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
            self.pending = None
        for image in self.cache.values():
            image.close()
        self.cache.clear()
        super().destroy()

    def bounds(self):
        if not self.tiles:
            return (0, 0, 256, 256)
        return (min(t['x'] for t in self.tiles), min(t['y'] for t in self.tiles),
                max(t['x'] + t.get('width', 256) for t in self.tiles),
                max(t['y'] + t.get('height', 256) for t in self.tiles))

    def fit(self):
        self.fit_bounds(self.bounds(), padding=20)

    def fit_bounds(self, bounds, padding=50):
        x0, y0, x1, y1 = bounds
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.scale = min(max(self.winfo_width() - padding, 100) / max(1, x1 - x0),
                         max(self.winfo_height() - padding, 100) / max(1, y1 - y0))
        self.scale = max(.025, min(8., self.scale))
        self.schedule()

    def zoom_to(self, scale, x=None, y=None):
        scale = max(.025, min(8., float(scale)))
        x = self.winfo_width() / 2 if x is None else x
        y = self.winfo_height() / 2 if y is None else y
        wx, wy = self.world(x, y)
        self.scale = scale
        self.cx = wx - (x - self.winfo_width() / 2) / scale
        self.cy = wy - (y - self.winfo_height() / 2) / scale
        self.schedule()

    def center(self, wx, wy, minimum_scale=None):
        self.cx, self.cy = wx, wy
        if minimum_scale is not None:
            self.scale = max(self.scale, minimum_scale)
        self.schedule()

    def move(self, dx, dy):
        self.cx += dx / self.scale
        self.cy += dy / self.scale
        self.schedule()

    def world(self, x, y):
        return (self.cx + (x - self.winfo_width() / 2) / self.scale,
                self.cy + (y - self.winfo_height() / 2) / self.scale)

    def screen(self, x, y):
        return ((x - self.cx) * self.scale + self.winfo_width() / 2,
                (y - self.cy) * self.scale + self.winfo_height() / 2)

    def tile_at(self, wx, wy):
        for tile in self.tiles:
            if tile['x'] <= wx < tile['x'] + tile.get('width', 256) and tile['y'] <= wy < tile['y'] + tile.get('height', 256):
                return tile
        return None

    def hit(self, x, y):
        found = [(abs(px - x) + abs(py - y), row) for px, py, row in self.hits if abs(px - x) < 11 and abs(py - y) < 11]
        return min(found, key=lambda item: item[0])[1] if found else None

    def press(self, event):
        self.focus_set()
        self.start = event.x, event.y, self.cx, self.cy
        self.dragging = False

    def drag(self, event):
        if self.start:
            x, y, cx, cy = self.start
            self.dragging = abs(event.x - x) + abs(event.y - y) > 3
            self.cx, self.cy = cx - (event.x - x) / self.scale, cy - (event.y - y) / self.scale
            self.schedule()

    def release(self, event):
        if not self.dragging:
            if self.route_editing and self.on_route_point:
                self.on_route_point(*self.world(event.x, event.y)); self.start = None; return
            marker = next((r for x, y, r in reversed(self.region_hits)
                           if abs(x - event.x) < 8 and abs(y - event.y) < 8), None)
            if marker and self.on_region_select:
                self.on_region_select(marker['iid'])
                self.start = None
                return
            record = self.hit(event.x, event.y)
            if event.state & 1 and self.on_edit:
                wx, wy = self.world(event.x, event.y)
                self.on_edit(record, self.tile_at(wx, wy), wx, wy)
                self.start = None
                return
            if record:
                self.selected = record['key']
                self.on_select(record)
                self.schedule()
            elif event.state & 4:
                wx, wy = self.world(event.x, event.y)
                tile = self.tile_at(wx, wy)
                if tile:
                    self.center(tile['x'] + tile.get('width', 256) / 2, tile['y'] + tile.get('height', 256) / 2)
        self.start = None

    def double_click(self, event):
        if self.route_editing and self.on_route_finish: self.on_route_finish()
        else: self.zoom_to(self.one_to_one_scale, event.x, event.y)

    def context(self, event):
        record = self.hit(event.x, event.y)
        wx, wy = self.world(event.x, event.y)
        self.on_context(event, record, self.tile_at(wx, wy), wx, wy)

    def hover(self, event):
        record = self.hit(event.x, event.y)
        if record:
            levels = (self.translate(' · niveau {minimum}–{maximum}').format(minimum=record.get('min_level', 0),
                                                                            maximum=record.get('max_level', 0))
                      if record.get('max_level') else '')
            self.status(record['name'] + levels)

    def schedule(self):
        if self.pending is None:
            self.pending = self.after(12, self.draw)

    def asset_image(self, tile):
        # A missing preview/HD variant must not hide a verified standard image.
        assets = ([tile.get('preview')] if self.scale < .35 else [])
        assets += ([tile.get('high')] if self.high else []) + [tile.get('standard')]
        failure = None
        for asset in assets:
            if not asset:
                continue
            key = (str(tile['root']), asset['path'])
            try:
                if key not in self.cache:
                    self.cache[key] = checked_image(tile['root'], asset)
                    while len(self.cache) > 32:
                        _, previous = self.cache.popitem(last=False)
                        previous.close()
                self.cache.move_to_end(key)
                return self.cache[key]
            except (OSError, ValueError) as error:
                failure = error
        if failure:
            raise failure
        return None

    def draw(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
        self.pending = None
        self.delete('all')
        self.photos, self.hits, self.region_hits = [], [], []
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        missing = []
        if not self.tiles:
            self.create_text(width / 2, height / 2, text=self.translate('Aucune carte disponible pour cette sélection.'), width=max(180, width - 80), justify='center')
        for tile in self.tiles:
            sx, sy = self.screen(tile['x'], tile['y'])
            tw, th = tile.get('width', 256) * self.scale, tile.get('height', 256) * self.scale
            if sx > width or sy > height or sx + tw < 0 or sy + th < 0:
                continue
            try:
                image = self.asset_image(tile)
                if image is None:
                    raise ValueError('Image absente')
                # Decode at native resolution, then only resize the visible crop.
                ix0 = max(0, math.floor(-sx / tw * image.width))
                iy0 = max(0, math.floor(-sy / th * image.height))
                ix1 = min(image.width, math.ceil((width - sx) / tw * image.width))
                iy1 = min(image.height, math.ceil((height - sy) / th * image.height))
                crop = image.crop((ix0, iy0, ix1, iy1))
                left, top = round(sx + ix0 / image.width * tw), round(sy + iy0 / image.height * th)
                right, bottom = round(sx + ix1 / image.width * tw), round(sy + iy1 / image.height * th)
                outw, outh = max(1, right - left), max(1, bottom - top)
                crop = crop.resize((outw, outh), Image.Resampling.BILINEAR)
                if self.dim:
                    crop = ImageEnhance.Brightness(crop).enhance(.55)
                photo = ImageTk.PhotoImage(crop)
                self.photos.append(photo)
                self.create_image(left, top, image=photo, anchor='nw')
            except (OSError, ValueError) as error:
                self.create_rectangle(sx, sy, sx + tw, sy + th, fill='#bababa', outline='#666666')
                missing.append(str(tile['id']))
        if len(self.region_outline) >= 3:
            coords = [value for point in self.region_outline for value in self.screen(*point)]
            self.create_line(*coords, *coords[:2], fill='#ffe35a', width=2)
        if self.paths_visible and self.annotations_visible:
            self.draw_native_paths(width, height)
        drawn = 0
        occupied = set()
        # User annotations must not disappear behind a dense historical layer.
        ordered = chain((row for row in self.records if row.get('source') == 'personal'),
                        (row for row in self.records if row.get('source') == 'community'),
                        (row for row in self.records if row.get('source') not in ('personal', 'community')))
        if not self.annotations_visible: ordered = ()
        for row in ordered:
            if self.category_filter is not None and row['category'] not in self.category_filter:
                continue
            category = self.categories.get(row['category'], {})
            marker_visible, label_visible = native_zoom_visibility(category, self.scale)
            if not marker_visible:
                continue
            px, py = self.screen(row['wx'], row['wy'])
            margin = 6 * self.marker_scale
            if not (-margin < px < width + margin and -margin < py < height + margin):
                continue
            cell = (int(px // 12), int(py // 12))
            if (drawn >= 1800 or cell in occupied) and row['key'] != self.selected and row.get('source') != 'personal':
                continue
            occupied.add(cell)
            drawn += 1
            self.hits.append((px, py, row))
            px, py = round(px), round(py)
            color = self.marker_color(row)
            # Keep the authored glyph and colour field on the same pixel grid.
            # Display scale is independent of terrain zoom and UI icon size.
            size = self.marker_scale
            elite = category.get('native_class') == 1 and (16 in (row.get('property_ids') or ()) or
                    any(str(name).casefold() in ('elite', 'élite') for name in (row.get('property_names') or ())))
            large = category.get('native_class') == 1 and (elite or row['category'] in (5, 6, 32))
            lower, upper = (-3, 4) if large else (-2, 3)
            self.create_rectangle(px + lower * size, py + lower * size, px + upper * size, py + upper * size,
                                  fill=color, outline='', width=0, tags=('annotation',))
            icon_category = 6 if elite and row['category'] == 7 else row['category']
            icon = self.icons.get(icon_category) or self.icons.get(row['category'])
            if icon:
                self.create_image(px - 5 * size, py - 5 * size, image=icon, anchor='nw', tags=('annotation',))
            if self.legend and label_visible:
                self.create_text(px + 6 * size, py, text=row['name'], fill=color, anchor='w', font=self.legend_font(row['category']), tags=('legend',))
        for marker in self.region_markers if self.annotations_visible else ():
            px, py = self.screen(marker['wx'], marker['wy'])
            if 0 <= px <= width and 0 <= py <= height:
                self.region_hits.append((px, py, marker))
                if self.region_icon:
                    self.create_image(px - 5 * self.marker_scale, py - 5 * self.marker_scale,
                                      image=self.region_icon, anchor='nw')
                else:
                    self.create_oval(px-4, py-4, px+4, py+4, fill='#ffe35a', outline='#333333')
        if missing:
            self.status(self.translate('{count} carte(s) absente(s) ou invalides dans cette vue ; aucune substitution.').format(count=len(missing)))
        self.on_view(self)

    def marker_color(self, row):
        category = self.categories.get(row['category'], {})
        if row['category'] in self.category_colors:
            category = dict(category, color_rgb=self.category_colors[row['category']])
        return native_marker_color(category, row, self.player_level, color_by_level=self.color_by_level)

    def legend_font(self, ident):
        if ident in self.category_fonts: return self.category_fonts[ident]
        category = self.categories.get(ident, {})
        styles = {0: 'normal', 1: 'bold', 2: 'italic', 3: 'bold italic'}
        size = category.get('font_size', 8)
        return (category.get('font_name') or 'Arial', size if 4 <= size <= 48 else 8,
                styles.get(category.get('font_style', 0), 'normal'))

    def draw_native_paths(self, width, height):
        if self.path_decoder is None and not self.personal_paths: return
        overlay = None
        paths = []
        for row in self.records:
            if not row.get('links') or (self.category_filter is not None and row['category'] not in self.category_filter): continue
            key = row['key']
            if key not in self.path_cache: self.path_cache[key] = self.path_decoder(row)
            path = self.path_cache[key]
            if path is None: continue
            if not path.always_visible and not native_zoom_visibility(self.categories.get(row['category'], {}), self.scale)[0]: continue
            color = self.marker_color(row)
            paths.append((path, color))
        paths.extend((path, '#ffb438') for path in self.personal_paths if path.always_visible or self.scale >= .35)
        for path, color in paths:
            if not path.points: continue
            points = [self.screen(x, y) for x, y in path.points]
            if (max(x for x, y in points) < 0 or min(x for x, y in points) > width or
                    max(y for x, y in points) < 0 or min(y for x, y in points) > height): continue
            if overlay is None: overlay = Image.new('RGBA', (width, height)); pen = ImageDraw.Draw(overlay)
            rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            if len(points) == 1:
                x, y = points[0]; pen.rectangle((x-2, y-2, x+2, y+2), fill=(*rgb, path.opacity)); continue
            if path.closed:
                pen.polygon(points, fill=(*rgb, path.fill_opacity))
                points.append(points[0])
            pen.line(points, fill=(*rgb, path.opacity), width=1)
        if overlay is not None:
            photo = ImageTk.PhotoImage(overlay); self.photos.append(photo)
            self.create_image(0, 0, image=photo, anchor='nw', tags=('native-paths',))

    def miniature(self, size=(150, 105)):
        x0, y0, x1, y1 = self.bounds()
        scale = min(size[0] / max(1, x1 - x0), size[1] / max(1, y1 - y0))
        image = Image.new('RGB', size, '#63859c')
        for tile in self.tiles:
            try:
                tile_image = self.asset_image(tile)
                if tile_image:
                    tile_image = tile_image.resize((max(1, round(tile.get('width', 256) * scale)), max(1, round(tile.get('height', 256) * scale))), Image.Resampling.BILINEAR)
                    image.paste(tile_image, (round((tile['x'] - x0) * scale), round((tile['y'] - y0) * scale)))
            except (OSError, ValueError):
                pass
        return image, (x0, y0, scale)
