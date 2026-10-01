"""Drawing-only bridge geometry. Physical bus identity decides connectivity."""
from bisect import bisect_left

EPS = .001


def _number(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.') if value else '0'


def _point(x, y):
    return f'{_number(x)} {_number(y)}'


def with_wire_crossings(scene):
    wires = []
    for bus in scene['buses']:
        ends = [branch['points'][-1] for branch in bus['branches']]
        if not ends:
            continue
        wires.append({'busId': bus['id'], 'branch': -1, 'points': [
            {'x': ends[0]['x'], 'y': min(p['y'] for p in ends)}, {'x': ends[0]['x'], 'y': max(p['y'] for p in ends)}]})
        wires.extend({'busId': bus['id'], 'branch': i, 'points': branch['points']} for i, branch in enumerate(bus['branches']))
    segments = []
    for wire_index, wire in enumerate(wires):
        for i, (a, b) in enumerate(zip(wire['points'], wire['points'][1:])):
            vertical = abs(a['x'] - b['x']) < EPS
            if not vertical and abs(a['y'] - b['y']) >= EPS:
                continue
            axis = 'y' if vertical else 'x'
            lo, hi = sorted((a[axis], b[axis]))
            if hi - lo > EPS:
                segments.append({'wire': wire_index, 'index': i, 'vertical': vertical, 'fixed': a['x' if vertical else 'y'], 'lo': lo, 'hi': hi})
    verticals = sorted((i for i, s in enumerate(segments) if s['vertical']), key=lambda i: segments[i]['fixed'])
    xs = [segments[i]['fixed'] for i in verticals]
    jumps = {}
    for h_index, h in enumerate(segments):
        if h['vertical']:
            continue
        i = bisect_left(xs, h['lo'] - EPS)
        while i < len(verticals) and xs[i] <= h['hi'] + EPS:
            v_index = verticals[i]
            v = segments[v_index]
            i += 1
            if wires[h['wire']]['busId'] == wires[v['wire']]['busId'] or not v['lo'] - EPS <= h['fixed'] <= v['hi'] + EPS:
                continue
            h_room = min(v['fixed'] - h['lo'], h['hi'] - v['fixed'])
            v_room = min(h['fixed'] - v['lo'], v['hi'] - h['fixed'])
            target = h_index if h_room > 3 else v_index if v_room > 3 else None
            if target is not None:
                jumps.setdefault(target, []).append(h['fixed'] if segments[target]['vertical'] else v['fixed'])
    gaps, bridges, emitted = {}, [], set()
    for segment_index, values in jumps.items():
        segment = segments[segment_index]
        ranges = []
        for at in sorted(set(values)):
            radius = min(6, at - segment['lo'] - 1, segment['hi'] - at - 1)
            start, end = at - radius, at + radius
            if ranges and start <= ranges[-1][1] + 2:
                ranges[-1][1] = max(ranges[-1][1], end)
            else:
                ranges.append([start, end])
        gaps[segment['wire'], segment['index']] = ranges
        for start, end in ranges:
            wire = wires[segment['wire']]
            key = wire['busId'], segment['vertical'], _number(segment['fixed']), _number(start), _number(end)
            if key in emitted:
                continue
            emitted.add(key)
            half = (end - start) / 2
            fixed = segment['fixed']
            path = (f'M {_point(fixed, start)} A 6 {_number(half)} 0 0 1 {_point(fixed, end)}' if segment['vertical'] else
                    f'M {_point(start, fixed)} A {_number(half)} 6 0 0 1 {_point(end, fixed)}')
            bridges.append({'busId': wire['busId'], 'branch': wire['branch'], 'path': path})
    paths = {}
    for index, wire in enumerate(wires):
        commands = [f"M {_point(wire['points'][0]['x'], wire['points'][0]['y'])}"]
        for i, (a, b) in enumerate(zip(wire['points'], wire['points'][1:])):
            vertical = abs(a['x'] - b['x']) < EPS
            forward = b['y'] >= a['y'] if vertical else b['x'] >= a['x']
            ranges = gaps.get((index, i), [])
            for r in ranges if forward else reversed(ranges):
                start, end = r if forward else reversed(r)
                commands.extend([f"L {_point(a['x'], start) if vertical else _point(start, a['y'])}",
                                 f"M {_point(a['x'], end) if vertical else _point(end, a['y'])}"])
            commands.append(f"L {_point(b['x'], b['y'])}")
        paths[wire['busId'], wire['branch']] = ' '.join(commands)
    return {**scene, 'crossingVersion': 1, 'wireBridges': bridges, 'buses': [
        {**bus, 'displayPath': paths.get((bus['id'], -1), bus.get('path', '')), 'branches': [
            {**branch, 'displayPath': paths.get((bus['id'], i), branch.get('path', ''))} for i, branch in enumerate(bus['branches'])]}
        for bus in scene['buses']]}
