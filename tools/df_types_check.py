#!/usr/bin/env python3
"""Compare DF type registries 26.2 vs 26.3, find replacements, check vein DF mapping."""
import json, os, re

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
V3 = f'{BASE}/vanilla-26.3/inner/data'
PACK = f'{BASE}/pack-extracted/data'

def L(p): return json.load(open(p))

reg3 = L(f'{BASE}/vanilla-26.3/report/generated/reports/registries.json')
df3 = set(reg3['minecraft:worldgen/density_function_type']['entries'])
print('=== 26.3 density_function_type registry (%d) ===' % len(df3))
for t in sorted(df3): print('  ', t)

print()
print('=== types used in vanilla 26.3 DF files ===')
used3 = set()
for root, _, files in os.walk(f'{V3}/minecraft/worldgen/density_function'):
    for f in files:
        used3 |= set(re.findall(r'"type":\s*"minecraft:([a-z_0-9]+)"', open(os.path.join(root, f)).read()))
for t in sorted(used3): print('  ', t)

print()
print('=== 26.3 overworld/preliminary_surface_level.json ===')
p = f'{V3}/minecraft/worldgen/density_function/overworld/preliminary_surface_level.json'
print(json.dumps(L(p), indent=1)[:800] if os.path.exists(p) else 'MISSING')

print()
print('=== 26.3 ore_vein DF files ===')
od = f'{V3}/minecraft/worldgen/density_function/overworld/ore_vein'
if os.path.isdir(od):
    for f in sorted(os.listdir(od)):
        d = L(f'{od}/{f}')
        print(f'--- {f}:', json.dumps(d, indent=1)[:350])
else:
    print('no ore_vein dir; searching...')
    for root, _, files in os.walk(f'{V3}/minecraft/worldgen/density_function'):
        for f in files:
            if 'vein' in f or 'vein' in root:
                print('  ', os.path.relpath(os.path.join(root, f), f'{V3}/minecraft/worldgen/density_function'))

print()
print('=== pack inline vein DFs (from noise_router) ===')
ns = L(f'{PACK}/minecraft/worldgen/noise_settings/overworld.json')
for k in ('vein_toggle', 'vein_ridged', 'vein_gap'):
    print(f'--- {k}:', json.dumps(ns['noise_router'][k], indent=1)[:350])
    print()

print('=== 26.2 vanilla vein fields for comparison ===')
v2ns = L(f'{BASE}/vanilla-26.2/inner/data/minecraft/worldgen/noise_settings/overworld.json')
for k in ('vein_toggle', 'vein_ridged', 'vein_gap'):
    a, b = v2ns['noise_router'][k], ns['noise_router'][k]
    print(f'{k}: pack == vanilla26.2 ->', json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
