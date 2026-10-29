#!/usr/bin/env python3
"""Recursive JSON diff + report of all remaining drift: placed_features, noise_settings, pack-vs-vanilla deltas."""
import json, os

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
V2 = f'{BASE}/vanilla-26.2/inner/data'
V3 = f'{BASE}/vanilla-26.3/inner/data'
PACK = f'{BASE}/pack-extracted'

def L(p): return json.load(open(p))

def diff(a, b, path=''):
    """Yield (path, a_val, b_val) for leaf differences."""
    if type(a) is not type(b):
        yield (path, a, b); return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: yield (f'{path}/{k}', None, b[k])
            elif k not in b: yield (f'{path}/{k}', a[k], None)
            else: yield from diff(a[k], b[k], f'{path}/{k}')
    elif isinstance(a, list):
        if len(a) != len(b):
            yield (path, f'<list len {len(a)}>', f'<list len {len(b)}>'); return
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff(x, y, f'{path}[{i}]')
    else:
        if a != b: yield (path, a, b)

drifted_pf = ['cave_vines', 'disk_grass', 'lush_caves_ceiling_vegetation', 'lush_caves_clay',
              'lush_caves_vegetation', 'pointed_dripstone', 'rooted_azalea_tree',
              'rooted_sulfur_spring', 'spore_blossom', 'sulfur_pool', 'sulfur_spike']

print('#' * 30, 'PLACED_FEATURE DRIFT (26.2 vs 26.3 vanilla)')
for name in drifted_pf:
    a, b = L(f'{V2}/minecraft/worldgen/placed_feature/{name}.json'), L(f'{V3}/minecraft/worldgen/placed_feature/{name}.json')
    ds = list(diff(a, b))
    print(f'--- {name}: {len(ds)} diffs')
    for p, x, y in ds[:8]:
        xs, ys = json.dumps(x)[:90], json.dumps(y)[:90]
        print(f'    {p}\n      26.2: {xs}\n      26.3: {ys}')
    if len(ds) > 8: print(f'    ... +{len(ds)-8} more')

print()
print('#' * 30, 'NOISE_SETTINGS/overworld 26.2 vs 26.3 (top-level)')
a, b = L(f'{V2}/minecraft/worldgen/noise_settings/overworld.json'), L(f'{V3}/minecraft/worldgen/noise_settings/overworld.json')
ds = list(diff(a, b))
print(f'total leaf diffs: {len(ds)}')
for p, x, y in ds[:25]:
    print(f'    {p}\n      26.2: {json.dumps(x)[:110]}\n      26.3: {json.dumps(y)[:110]}')
if len(ds) > 25: print(f'    ... +{len(ds)-25} more')

print()
print('#' * 30, 'PACK dimension_type vs 26.2 vanilla (pack intent)')
a, b = L(f'{V2}/minecraft/dimension_type/overworld.json'), L(f'{PACK}/data/minecraft/dimension_type/overworld.json')
ds = list(diff(a, b))
for p, x, y in ds:
    print(f'    {p}\n      van26.2: {json.dumps(x)[:110]}\n      pack   : {json.dumps(y)[:110]}')
