#!/usr/bin/env python3
"""Deep checks for noise_settings port: surface level DFs, vein mechanism, type validation, random_offset scan."""
import json, os, re

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
V2 = f'{BASE}/vanilla-26.2/inner/data'
V3 = f'{BASE}/vanilla-26.3/inner/data'
PACK = f'{BASE}/pack-extracted/data'

def L(p): return json.load(open(p))

print('=== 1. preliminary_surface_level comparison ===')
pack_ns = L(f'{PACK}/minecraft/worldgen/noise_settings/overworld.json')
pack_psl = pack_ns['noise_router']['preliminary_surface_level']
v2_ns = L(f'{V2}/minecraft/worldgen/noise_settings/overworld.json')
v2_psl = v2_ns['noise_router']['preliminary_surface_level']
v3_csl = L(f'{V3}/minecraft/worldgen/density_function/overworld/chunk_surface_level.json')
print('pack == van26.2 preliminary_surface_level:', json.dumps(pack_psl, sort_keys=True) == json.dumps(v2_psl, sort_keys=True))
print('van26.3 chunk_surface_level file:')
print(json.dumps(v3_csl, indent=1)[:400])
print('van26.2 preliminary_surface_level:')
print(json.dumps(v2_psl, indent=1)[:400])

print()
print('=== 2. pack noise sub-object ===')
print(json.dumps(pack_ns['noise']))
print('pack default_block:', json.dumps(pack_ns['default_block']))
print('pack default_fluid:', json.dumps(pack_ns['default_fluid']))
print('pack spawn_target:', json.dumps(pack_ns.get('spawn_target'))[:120])

print()
print('=== 3. 26.3 vein material rule ===')
p = f'{V3}/minecraft/worldgen/material_rule/overworld'
print('dir contents:', os.listdir(p))
cv = L(f'{p}/copper_ore_vein.json')
print(json.dumps(cv, indent=1)[:700])

print()
print('=== 4. type validation: pack density_functions + surface_rule vs 26.3 registries ===')
reg = L(f'{BASE}/vanilla-26.3/report/generated/reports/registries.json')
df_types = set(reg['minecraft:worldgen/density_function_type']['entries'])
mc_types = set(reg['minecraft:worldgen/material_condition_type']['entries'])
mr_types = set(reg['minecraft:worldgen/material_rule_type']['entries'])

used_df, used_mc, used_mr = set(), set(), set()
for root, _, files in os.walk(f'{PACK}/minecraft/worldgen/density_function'):
    for f in files:
        s = open(os.path.join(root, f)).read()
        used_df |= set(re.findall(r'"type":\s*"minecraft:([a-z_0-9]+)"', s))
ns_str = json.dumps(pack_ns)
# surface rule conditions + rules
for t in re.findall(r'"type":\s*"minecraft:([a-z_0-9]+)"', json.dumps(pack_ns['surface_rule'])):
    used_mc.add(t); used_mr.add(t)
# noise router inline DFs
for k in ('preliminary_surface_level', 'vein_toggle', 'vein_ridged', 'vein_gap'):
    for t in re.findall(r'"type":\s*"minecraft:([a-z_0-9]+)"', json.dumps(pack_ns['noise_router'][k])):
        used_df.add(t)

df_missing = sorted(t for t in used_df if f'minecraft:{t}' not in df_types)
mc_missing = sorted(t for t in used_mc if f'minecraft:{t}' not in mc_types and f'minecraft:{t}' not in mr_types)
mr_missing = sorted(t for t in used_mr if f'minecraft:{t}' not in mr_types and f'minecraft:{t}' not in mc_types)
print('DF types used by pack:', len(used_df), '| missing in 26.3:', df_missing or 'NONE')
print('material-condition types used:', len(used_mc), '| missing:', mc_missing or 'NONE')
print('material-rule types used:', len(used_mr), '| missing:', mr_missing or 'NONE')

print()
print('=== 5. random_offset usage across ALL pack files ===')
hits = []
for root, _, files in os.walk(f'{PACK}/minecraft'):
    for f in files:
        s = open(os.path.join(root, f)).read()
        if 'random_offset' in s:
            hits.append(os.path.relpath(os.path.join(root, f), f'{PACK}/minecraft'))
for h in sorted(hits): print('  ', h)
print('total:', len(hits))

print()
print('=== 6. block-state vs string: default_block/fluid style in 26.3 ===')
print('van26.3 noise_settings default_block type:', type(v3 := L(f'{V3}/minecraft/worldgen/noise_settings/overworld.json')) and type(v3['default_block']).__name__)
