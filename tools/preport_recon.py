#!/usr/bin/env python3
"""Final pre-port reconnaissance: pack DF type usage w/ fields, surface_rule structure, vein equality."""
import json, os, re
from collections import defaultdict

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
PACK = f'{BASE}/pack-extracted/data'

def walk_types(o, acc):
    if isinstance(o, dict):
        t = o.get('type')
        if isinstance(t, str) and t.startswith('minecraft:'):
            acc[t[10:]].update(k for k in o if k != 'type')
        for v in o.values(): walk_types(v, acc)
    elif isinstance(o, list):
        for v in o: walk_types(v, acc)
    return acc

acc = defaultdict(set)
for root, _, files in os.walk(f'{PACK}/minecraft/worldgen/density_function'):
    for f in files:
        walk_types(json.load(open(os.path.join(root, f))), acc)
ns = json.load(open(f'{PACK}/minecraft/worldgen/noise_settings/overworld.json'))
for k in ('preliminary_surface_level', 'vein_toggle', 'vein_ridged', 'vein_gap'):
    walk_types(ns['noise_router'][k], acc)

print('=== PACK DF types + fields used ===')
for t in sorted(acc): print(f'  {t}: {sorted(acc[t])}')

print()
print('=== pack surface_rule root ===')
sr = ns['surface_rule']
print('root type:', sr.get('type'))
if sr.get('type', '').endswith('sequence'):
    seq = sr['sequence']
    print('sequence entries:', len(seq))
    for i, e in enumerate(seq):
        t = e.get('type', '?')
        desc = ''
        if t == 'minecraft:condition':
            cond = e.get('if_true', {})
            desc = 'cond:' + cond.get('type', '?')
            if 'biome_is' in cond: desc += ' ' + json.dumps(cond['biome_is'])
            if 'noise' in cond: desc += ' ' + cond['noise']
        elif t == 'minecraft:block':
            desc = json.dumps(e.get('result_state', {}))[:60]
        else:
            desc = json.dumps(e)[:60]
        print(f'  [{i}] {t} {desc}')
elif 'sequence' in sr:
    print('sequence len', len(sr['sequence']))
else:
    print(json.dumps(sr)[:300])

print()
print('=== pack veins == 26.2 vanilla veins? ===')
v2ns = json.load(open(f'{BASE}/vanilla-26.2/inner/data/minecraft/worldgen/noise_settings/overworld.json'))
for k in ('vein_toggle', 'vein_ridged', 'vein_gap'):
    a, b = v2ns['noise_router'][k], ns['noise_router'][k]
    print(f'  {k}:', json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

print()
print('=== pack preliminary_surface_level vs 26.2 vanilla ===')
a = v2ns['noise_router']['preliminary_surface_level']
b = ns['noise_router']['preliminary_surface_level']
print('identical:', json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

print()
print('=== pack biome spawn_costs non-empty? ===')
for f in sorted(os.listdir(f'{PACK}/minecraft/worldgen/biome')):
    b = json.load(open(f'{PACK}/minecraft/worldgen/biome/{f}'))
    sc = b.get('spawn_costs', {})
    if sc: print('  ', f, json.dumps(sc)[:150])
print('done')
