"""Measure actual Tk rendering and local data coverage in an isolated profile."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile
import time

from tools.clone_app import Application, VERSION
from tools.clone_regions import decode_region_outline


def measure(data):
    result = {'version': VERSION, 'scope': 'Source client, real Tk windows and local data; not packaged startup or in-game proof', 'milliseconds': {}}
    with tempfile.TemporaryDirectory(prefix='wcf-performance-') as directory:
        start = time.perf_counter()
        app = Application(data, Path(directory) / 'annotations.sqlite3', offline=True)
        app.root.update(); app.initial_view(); app.root.update()
        result['milliseconds']['startup_and_first_map'] = (time.perf_counter() - start) * 1000
        def timed(name, action):
            before = time.perf_counter(); action(); app.root.update(); app.map.draw()
            result['milliseconds'][name] = (time.perf_counter() - before) * 1000
        try:
            region = next(iid for iid in app.groups if app.regions.item(iid, 'text') == 'Féralas')
            timed('open_feralas', lambda: app.select_region_marker(region))
            timed('zoom', lambda: app.map.zoom_to(app.map.scale * 1.25, 250, 250))
            timed('pan', lambda: app.map.move(100, 50))
            timed('switch_to_modern_ui', lambda: app.set_interface('Modern'))
            timed('switch_to_legacy_ui', lambda: app.set_interface('Legacy'))
            app.query.set('Azshara')
            timed('search_azshara_and_render_page', app.search)
            result['azshara_results'] = len(app.search_matches)
            category = app.model.category_counts.most_common(1)[0][0]
            before = time.perf_counter(); matches = app.model.search(categories={category})
            result['milliseconds']['largest_category_search_model'] = (time.perf_counter() - before) * 1000
            result['largest_category'] = dict(id=category, results=len(matches), name=app.model.categories[category]['name'])
            before = time.perf_counter()
            ident = app.store.add_note(dict(name='Mesure isolée', map_id=17, x=25000, y=30000,
                                           source_ref=app.model.personal_prefix + 'measure'))
            app.refresh_local_annotations(); app.root.update()
            result['milliseconds']['add_and_refresh'] = (time.perf_counter() - before) * 1000
            before = time.perf_counter(); app.store.update_note(ident, dict(comment='Modification isolée'))
            app.refresh_local_annotations(); app.root.update()
            result['milliseconds']['edit_and_refresh'] = (time.perf_counter() - before) * 1000
            result['coverage'] = []
            for spec in app.model.sets:
                for locale in spec.get('databases', {}):
                    app.model.open(spec['id'], locale)
                    missing = [dict(id=t['id'], filename=t['filename'], group_id=t['group_id'])
                               for t in app.model.tiles.values() if t.get('standard') is None]
                    result['coverage'].append(dict(map_set=spec['id'], locale=locale,
                        source_sha256=app.model.db['source_sha256'],
                        annotations=len(app.model.db['annotations']), projected=len(app.model.annotations),
                        categories=[dict(id=ident, name=c['name'], records=app.model.category_counts[ident]) for ident,c in app.model.categories.items()],
                        tiles=len(app.model.tiles), missing=missing,
                        geographic_regions=len(app.model.geographic_regions()),
                        regions_with_outline=sum(bool(decode_region_outline(r)) for r in app.model.geographic_regions())))
        finally:
            app.close()
    result['milliseconds'] = {key: round(value, 2) for key, value in result['milliseconds'].items()}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = measure(args.data)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['milliseconds'], indent=2))
