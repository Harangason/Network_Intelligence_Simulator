"""Read-only geometry comparison against an exported network-view JSON."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.network_scene import build_network_scene, model_signature


def segments(bus):
    anchors = [branch['points'][-1] for branch in bus['branches']]
    trunk = sorted(anchors, key=lambda p: p['y'])
    return [(trunk[0], trunk[-1]), *[(a, b) for branch in bus['branches'] for a, b in zip(branch['points'], branch['points'][1:]) if a != b]]


def crossings(buses):
    intersections, overlaps = set(), set()
    for index, left in enumerate(buses):
        for right in buses[index + 1:]:
            for a, b in segments(left):
                for c, d in segments(right):
                    av, cv = a['x'] == b['x'], c['x'] == d['x']
                    if av != cv:
                        v1, v2, h1, h2 = (a, b, c, d) if av else (c, d, a, b)
                        if min(v1['y'], v2['y']) < h1['y'] < max(v1['y'], v2['y']) and min(h1['x'], h2['x']) < v1['x'] < max(h1['x'], h2['x']):
                            intersections.add((left['id'], right['id'], round(v1['x'], 2), round(h1['y'], 2)))
                    else:
                        axis, fixed = ('y', 'x') if av else ('x', 'y')
                        if abs(a[fixed] - c[fixed]) < .001 and min(max(a[axis], b[axis]), max(c[axis], d[axis])) - max(min(a[axis], b[axis]), min(c[axis], d[axis])) > .001:
                            overlaps.add((left['id'], right['id']))
    return {'crossings': len(intersections), 'overlappingBusPairs': len(overlaps)}


if __name__ == '__main__':
    source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    topology = source['topology']
    positions = {n['id']: {key: n[key] for key in ('x', 'y', 'width', 'height')} for n in topology['nodes']}
    updated = build_network_scene(topology, positions=positions, bus_routes={})
    assert model_signature(updated) == model_signature(topology)
    owner = next(n for n in topology['nodes'] if n['name'] == 'Bremsregelung')
    old = [b for b in topology['scene']['buses'] if b['frameId'] == owner['id']]
    new = [b for b in updated['scene']['buses'] if b['frameId'] == owner['id']]
    report = {'frame': owner['name'], 'buses': len(new), 'before': crossings(old), 'after': crossings(new),
              'warnings': updated['scene']['routingWarnings'], 'modelUnchanged': True}
    Path('backend/runtime/wire-layout-geometry.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
