#!/usr/bin/env python3
"""
JJThunder To The Max v0.9.0 (26.2) -> Minecraft 26.3 porter.

Strategy: "port + tweak"
  - vanilla 26.3 file = base (new format + Mojang's 26.3 content)
  - pack's 26.2 deltas vs vanilla 26.2 = author intent, reapplied on top
  - pack-custom files = syntax-migrated only
Documented in PORT_NOTES.md.
"""
import json, os, shutil, zipfile, re

BASE = '/home/z/my-project/JJthunderToTheMaxPort'
WORK = f'{BASE}/work'
V2 = f'{WORK}/vanilla-26.2/inner/data'
V3 = f'{WORK}/vanilla-26.3/inner/data'
PACK = f'{WORK}/pack-extracted'
PORT = f'{BASE}/pack-26.3'
REPORT = f'{WORK}/vanilla-26.3/report/generated/reports'

NOTES = []          # (section, line) port notes
def note(section, line): NOTES.append((section, line))

# ---------------- helpers ----------------
def L(p):
    with open(p) as f: return json.load(f)

BLOCKS = L(f'{REPORT}/blocks.json') if os.path.exists(f'{REPORT}/blocks.json') else {}
STATE_ERRORS = []

def state_to_string(st, ctx):
    """26.2 block-state object -> 26.3 block-id string (validated against blocks.json)."""
    if isinstance(st, str): return st
    name = st.get('Name')
    props = st.get('Properties', {})
    if not props: return name
    entry = BLOCKS.get(name)
    if not entry:
        STATE_ERRORS.append(f'{ctx}: unknown block {name}')
        return name
    match = None
    for s in entry['states']:
        if s.get('properties', {}) == props: match = s; break
    if match is None and not entry.get('properties'):
        # block has no properties at all - the 26.2 Properties were junk that the old
        # codec silently ignored (e.g. ice with level=0); fall back to the plain block
        return name
    if match is None:
        STATE_ERRORS.append(f'{ctx}: {name} has no state {props}')
        return name
    if match.get('default'):
        return name                      # default state -> plain id
    order = list(entry['properties'].keys())
    s = name + '[' + ','.join(f'{k}={props[k]}' for k in order if k in props) + ']'
    STATE_ERRORS.append(f'{ctx}: NON-default state {name}{props} -> trying string syntax {s}')
    return s

def migrate_feature_json(o, ctx):
    """Recursively: flatten {type, config} envelopes (26.3 removed 'config');
    convert block-state objects to id strings."""
    if isinstance(o, list):
        return [migrate_feature_json(x, ctx) for x in o]
    if not isinstance(o, dict):
        return o
    if 'Name' in o and isinstance(o.get('Name'), str) and ('Properties' in o or len(o) == 1):
        return state_to_string(o, ctx)
    out = {}
    for k, v in o.items():
        if k == 'config' and isinstance(v, dict) and 'type' in o:
            for k2, v2 in v.items():
                out[k2] = migrate_feature_json(v2, ctx)
        else:
            out[k] = migrate_feature_json(v, ctx)
    return out

def W(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write('\n')

def canon(o):
    if isinstance(o, bool): return o
    if isinstance(o, (int, float)): return round(float(o), 6)
    if isinstance(o, dict): return {k: canon(v) for k, v in sorted(o.items())}
    if isinstance(o, list): return [canon(x) for x in o]
    return o

def numnorm_color(v):
    """int color -> '#RRGGBB'; hex string -> lowercase"""
    if isinstance(v, int) and not isinstance(v, bool):
        return f'#{v & 0xFFFFFF:06x}'.lower()
    if isinstance(v, str) and re.fullmatch(r'#?[0-9a-fA-F]{6,8}', v or ''):
        return ('#' + v.lstrip('#'))[-8:].lower()
    return canon(v)

# ---------------- DF migration (26.2 syntax -> 26.3 syntax) ----------------
BINARY_OPS = {'minecraft:add', 'minecraft:sub', 'minecraft:mul', 'minecraft:min',
              'minecraft:max', 'minecraft:div', 'minecraft:pow'}
UNARY_INPUT = {'minecraft:abs', 'minecraft:negate', 'minecraft:square', 'minecraft:cube',
               'minecraft:half_negative', 'minecraft:quarter_negative', 'minecraft:squeeze',
               'minecraft:ceil', 'minecraft:floor', 'minecraft:sqrt', 'minecraft:blend_density'}

def df_migrate(o, stats):
    """Recursively migrate a density function (or arbitrary JSON) to 26.3 syntax."""
    if isinstance(o, list):
        return [df_migrate(x, stats) for x in o]
    if not isinstance(o, dict):
        return o
    t = o.get('type')
    out = {k: df_migrate(v, stats) for k, v in o.items()}
    if t in BINARY_OPS:
        if 'argument1' in out: out['left'] = out.pop('argument1'); stats['binary_renamed'] += 1
        if 'argument2' in out: out['right'] = out.pop('argument2'); stats['binary_renamed'] += 1
    elif t == 'minecraft:clamp':
        if 'argument' in out: out['input'] = out.pop('argument'); stats['unary_renamed'] += 1
    elif t in UNARY_INPUT:
        if 'argument' in out: out['input'] = out.pop('argument'); stats['unary_renamed'] += 1
    elif t in ('minecraft:cache_2d', 'minecraft:flat_cache'):
        out = {'type': 'minecraft:cache', 'input': df_migrate(o['argument'], stats)}
        stats[t.split(':')[1] + '_to_cache'] += 1
    elif t == 'minecraft:interpolated':
        out = {'type': 'minecraft:interpolated',
               'cell_size_xz': 4, 'cell_size_y': 4,   # pack 26.2 noise size 1/1 -> cells 4x4 (see PORT_NOTES)
               'input': df_migrate(o['argument'], stats)}
        stats['interpolated_cell'] += 1
    elif t == 'minecraft:shifted_noise':
        out = {'type': 'minecraft:noise'}
        for k in ('noise', 'shift_x', 'shift_z', 'xz_scale', 'y_scale'):
            if k in o: out[k] = df_migrate(o[k], stats)
        if 'shift_y' in o:
            stats['shift_y_dropped'] += 1
            if o['shift_y'] not in (0, 0.0):
                note('density-functions', f'shift_y={o["shift_y"]} dropped in shifted_noise (field was ignored by 26.2 too)')
        stats['shifted_noise_to_noise'] += 1
    elif t == 'minecraft:y_clamped_gradient':
        out = {'type': 'minecraft:gradient', 'axis': 'y',
               'from_coordinate': o['from_y'], 'to_coordinate': o['to_y'],
               'from_value': o['from_value'], 'to_value': o['to_value']}
        stats['y_gradient'] += 1
    return out

# ---------------- start: copy pack ----------------
if os.path.exists(PORT): shutil.rmtree(PORT)
shutil.copytree(PACK, PORT)
note('overview', 'Copied all 279 pack files as base; every vanilla-shared file that was '
                 'schema-identical in 26.2/26.3 (structures, structure sets, tag, most placed features) is kept as-is.')

stats = {'binary_renamed': 0, 'unary_renamed': 0, 'cache_2d_to_cache': 0, 'flat_cache_to_cache': 0,
         'interpolated_cell': 0, 'shifted_noise_to_noise': 0, 'y_gradient': 0, 'shift_y_dropped': 0}

# ---------------- 1. configured_carver: registry removed in 26.3 ----------------
cc_dir = f'{PORT}/data/minecraft/worldgen/configured_carver'
if os.path.isdir(cc_dir):
    shutil.rmtree(cc_dir)
note('carvers', 'Removed configured_carver/{cave,cave_extra_underground,canyon}.json - the '
                'worldgen/configured_carver registry no longer exists in 26.3 (carvers are code-built-in). '
                'The original pack disabled vanilla carving via probability:0 in those files; the same '
                'result is preserved by emptying the carvers list in every ported biome.')

# ---------------- 2. placed_feature: random_offset -> offset ----------------
pf_dir = f'{PORT}/data/minecraft/worldgen/placed_feature'
pf_migrated = 0
for f in os.listdir(pf_dir):
    p = f'{pf_dir}/{f}'
    d = L(p)
    changed = False
    for pl in d.get('placement', []):
        if pl.get('type') == 'minecraft:random_offset':
            pl.clear()
            pl['type'] = 'minecraft:offset'
            # rebuild preserving order: type, x, y, z (x=z=old xz_spread, y=old y_spread)
            old = L(p)['placement'][[i for i, q in enumerate(L(p)['placement'])
                                     if q.get('type') == 'minecraft:random_offset'][0]]
            pl['type'] = 'minecraft:offset'
            pl['x'] = old.get('xz_spread', 0)
            pl['y'] = old.get('y_spread', 0)
            pl['z'] = old.get('xz_spread', 0)
            changed = True
    if changed:
        W(p, d); pf_migrated += 1
note('placed-features', f'{pf_migrated} placed features migrated: placement modifier '
                        '"minecraft:random_offset"{xz_spread,y_spread} renamed to '
                        '"minecraft:offset"{x,y,z} (x=z=old xz_spread, y=old y_spread) per 26.3 vanilla files.')

# ---------------- 2b. configured_feature -> feature (registry dir renamed in 26.3) ----------------
cf_src = f'{PORT}/data/minecraft/worldgen/configured_feature'
cf_dst = f'{PORT}/data/minecraft/worldgen/feature'
n_cf = 0
if os.path.isdir(cf_src):
    os.makedirs(cf_dst, exist_ok=True)
    for f in os.listdir(cf_src):
        d = L(f'{cf_src}/{f}')
        d = migrate_feature_json(d, f'feature/{f}')
        W(f'{cf_dst}/{f}', d)
        n_cf += 1
    shutil.rmtree(cf_src)
note('features', f'Renamed registry directory worldgen/configured_feature -> worldgen/feature (26.3 rename; '
                f'the old directory is silently ignored, which left the pack custom features '
                f'(frozen_delta_deepslate, frozen_delta_tuff, water_delta) unbound). {n_cf} feature files migrated: '
                f'the config envelope is flattened to top level and block states are written as block-id strings '
                f'(validated against the official 26.3 blocks report).')

# ---------------- 2c. noise files -> 26.3 schema ----------------
# base_amplitude is Mojang per-profile normalization constant; it depends only on the amplitude
# profile with trailing zeros stripped (proven by identical constants for (1,1) vs (1,1,0,0,0,0)).
NOISE_BASE = {
    (1.0,):                    0.955388882960065,
    (1.0, 1.0):                0.9494731054427981,
    (1.0, 1.0, 1.0):           0.9381732587751008,
    (1.0, 1.0, 1.0, 1.0):      0.939546696581729,
    (1.0, 0.0, 1.0):           1.1817507833955654,
    (1.0, 1.0, 0.0, 1.0):      1.0582769165096106,
    (1.0, 1.0, 0.0, 1.0, 1.0): 1.063180125160734,
    (1.0, 2.0, 1.0):           0.9147152149950137,
    (1.5, 0.0, 1.0):           1.2453007926713473,
}
noise_dir = f'{PORT}/data/minecraft/worldgen/noise'
n_noises = 0
for f in os.listdir(noise_dir):
    p = f'{noise_dir}/{f}'
    if not f.endswith('.json'): continue
    d = L(p)
    if 'firstOctave' not in d: continue
    A = [float(x) for x in d['amplitudes']]
    stripped = list(A)
    while stripped and stripped[-1] == 0.0: stripped.pop()
    key = tuple(stripped) if stripped else (1.0,)
    if key not in NOISE_BASE:
        STATE_ERRORS.append(f'noise/{f}: unknown amplitude profile {key}')
        continue
    out = {'base_octave': d['firstOctave'], 'base_amplitude': NOISE_BASE[key]}
    if len(A) > 1: out['octave_count'] = len(A)
    if any(x != 1.0 for x in A): out['amplitude_modifiers'] = A
    W(p, out)
    n_noises += 1
note('noise', f'{n_noises} noise parameter sets migrated to the 26.3 schema (firstOctave/amplitudes -> '
              f'base_octave/base_amplitude/octave_count/amplitude_modifiers). base_amplitude is Mojang '
              f'per-profile normalization constant; exact values were taken from the 26.3 vanilla noise set, '
              f'because every pack noise profile is either a verbatim vanilla profile (erosion_med == erosion, '
              f'temperature_med == temperature, vegetation_med == vegetation) or collapses to one '
              f'(cave -> [1,1], island -> [1]; trailing zero amplitudes are ignored by the normalization).')

# ---------------- 3. density_function files: syntax migration ----------------
df_dir = f'{PORT}/data/minecraft/worldgen/density_function'
df_migrated = 0
for root, _, files in os.walk(df_dir):
    for f in files:
        p = os.path.join(root, f)
        d = L(p)
        before = json.dumps(d, sort_keys=True)
        d2 = df_migrate(d, stats)
        if json.dumps(d2, sort_keys=True) != before:
            W(p, d2); df_migrated += 1
note('density-functions', f'{df_migrated} of 170 density function files syntax-migrated to 26.3: '
                          'argument1/argument2 -> left/right; unary .argument -> .input; cache_2d/flat_cache -> cache; '
                          'shifted_noise -> noise (shift_y dropped, it was ignored by 26.2 as well); '
                          'y_clamped_gradient -> gradient(axis=y); interpolated gains explicit cell sizes 4x4 '
                          '(original pack used noise size_horizontal=1/size_vertical=1, i.e. 4x4 blocks per cell).')

# ---------------- 4. biomes: 3-way merge ----------------
CATS = ('monster', 'creature', 'ambient', 'axolotls', 'underground_water_creature',
        'water_creature', 'water_ambient', 'misc')

def pack_spawn_set(pfile):
    d = L(pfile); out = {}
    for cat, sp in d.get('spawners', {}).items():
        out[cat] = sorted((s['type'], s['weight'], int(s['minCount']), int(s['maxCount'])) for s in sp)
    return out

def van_spawn_set(vfile):
    d = L(vfile); out = {}
    nms = d.get('attributes', {}).get('minecraft:gameplay/natural_mob_spawns')
    if not nms: return out
    for cat, sp in nms['argument'].get('spawns_by_category', {}).items():
        lst = []
        for s in sp:
            c = s['count']
            if isinstance(c, dict):
                lst.append((s['type'], s['weight'], int(c['min_inclusive']), int(c['max_inclusive'])))
            else:
                lst.append((s['type'], s['weight'], int(c), int(c)))
        out[cat] = sorted(lst)
    return out

def pack_counts_to_new(lst):
    out = []
    for (typ, wgt, mn, mx) in lst:
        cnt = mn if mn == mx else {'type': 'minecraft:uniform', 'min_inclusive': mn, 'max_inclusive': mx}
        out.append({'type': typ, 'weight': wgt, 'count': cnt})
    return out

biome_src = f'{PORT}/data/minecraft/worldgen/biome'
b_ident = b_merged = b_custom = 0
for f in sorted(os.listdir(biome_src)):
    P = L(f'{biome_src}/{f}')
    v2p, v3p = f'{V2}/minecraft/worldgen/biome/{f}', f'{V3}/minecraft/worldgen/biome/{f}'
    has_v2, has_v3 = os.path.exists(v2p), os.path.exists(v3p)

    # carvers: pack kills vanilla carvers globally (probability 0); registry gone -> force []
    P['carvers'] = []

    if has_v2 and has_v3:
        V2b, V3b = L(v2p), L(v3p)
        R = json.loads(json.dumps(V3b))  # deep copy of 26.3 vanilla = base

        # top-level scalars: temperature / downfall / has_precipitation
        for k in ('temperature', 'downfall', 'has_precipitation'):
            if k in P and canon(P.get(k)) != canon(V2b.get(k)):
                R[k] = P[k]
        # any other top-level keys the pack added that vanilla lacks
        for k in P:
            if k in ('spawners', 'spawn_costs', 'carvers', 'attributes', 'effects', 'features',
                     'creature_spawn_probability', 'temperature', 'downfall', 'has_precipitation'):
                continue
            if canon(P[k]) != canon(V2b.get(k)):
                R[k] = P[k]

        # effects merge (per key, color-normalized)
        eff = json.loads(json.dumps(R.get('effects', {})))
        pe, v2e = P.get('effects', {}), V2b.get('effects', {})
        for k in sorted(set(pe) | set(v2e)):
            pv, v2v = pe.get(k), v2e.get(k)
            if pv is None: continue
            if numnorm_color(pv) == numnorm_color(v2v):
                continue                      # same as 26.2 vanilla -> keep 26.3 value
            if numnorm_color(pv) != numnorm_color(v2v):
                eff[k] = pv                   # real pack change -> pack wins
        R['effects'] = eff
        R['carvers'] = []   # pack intent: vanilla carving disabled (see carvers note)

        # features: per-step merge
        pf, v2f, v3f = P.get('features', []), V2b.get('features', []), R.get('features', [])
        steps = []
        for i in range(max(len(pf), len(v2f), len(v3f))):
            a = canon(pf[i]) if i < len(pf) else None
            b = canon(v2f[i]) if i < len(v2f) else None
            if a is not None and a != b: steps.append(pf[i])
            elif i < len(v3f): steps.append(v3f[i])
            elif i < len(pf): steps.append(pf[i])
            else: steps.append([])
        R['features'] = steps

        # creature_spawn_probability -> attribute
        p_csp = P.get('creature_spawn_probability')
        if p_csp is not None and canon(p_csp) != canon(V2b.get('creature_spawn_probability', 0.1)):
            R.setdefault('attributes', {})['minecraft:gameplay/creature_world_gen_spawn_probability'] = p_csp

        # spawners: if pack content differs from 26.2 vanilla -> rebuild attribute from pack data
        ps, vs = pack_spawn_set(f'{biome_src}/{f}'), van_spawn_set(v2p)
        if ps != vs:
            arg = R.setdefault('attributes', {}).setdefault(
                'minecraft:gameplay/natural_mob_spawns',
                {'argument': {'spawn_costs': {}, 'spawns_by_category': {}}, 'modifier': 'overlay'})['argument']
            arg['spawn_costs'] = arg.get('spawn_costs', {})
            arg['spawns_by_category'] = {c: pack_counts_to_new(ps[c]) for c in CATS if ps.get(c)}
            b_merged += 1
        else:
            b_ident += 1
        W(f'{biome_src}/{f}', R)
    else:
        # pack-custom biome: format migration in place
        ps = pack_spawn_set(f'{biome_src}/{f}')
        attrs = P.get('attributes', {})
        attrs['minecraft:gameplay/natural_mob_spawns'] = {
            'argument': {'spawn_costs': P.get('spawn_costs', {}),
                         'spawns_by_category': {c: pack_counts_to_new(ps[c]) for c in CATS if ps.get(c)}},
            'modifier': 'overlay'}
        if 'creature_spawn_probability' in P:
            attrs['minecraft:gameplay/creature_world_gen_spawn_probability'] = P.pop('creature_spawn_probability')
        P['attributes'] = attrs
        P.pop('spawners', None); P.pop('spawn_costs', None)
        W(f'{biome_src}/{f}', P)
        b_custom += 1

note('biomes', f'All {b_ident + b_merged + b_custom} biome files migrated to the 26.3 format '
               f'(mob spawning moved from top-level spawners/spawn_costs to '
               f'attributes/minecraft:gameplay/natural_mob_spawns; creature_spawn_probability -> '
               f'attributes/minecraft:gameplay/creature_world_gen_spawn_probability). '
               f'{b_ident} were content-identical to vanilla (kept 26.3 vanilla content), '
               f'{b_merged} had pack spawn overrides reapplied, {b_custom} are pack-custom biomes. '
               f'Author intent (temperature, colors, features, spawn weights) verified against vanilla 26.2 '
               f'and reapplied only where the pack actually differed from it.')
note('biomes', 'carvers set to [] in every ported biome (see carvers note).')

# ---------------- 5. noise_settings/overworld.json rebuild ----------------
ns = L(f'{PORT}/data/minecraft/worldgen/noise_settings/overworld.json')
nr_old = ns['noise_router']

# 5a. pack preliminary_surface_level -> density_function/overworld/preliminary_surface_level.json
psl = df_migrate(nr_old['preliminary_surface_level'], stats)
W(f'{PORT}/data/minecraft/worldgen/density_function/overworld/preliminary_surface_level.json', psl)
note('noise-settings', 'Pack\'s modified preliminary_surface_level (retuned for the 2096-block tall world) '
                       'migrated and written to density_function/overworld/preliminary_surface_level.json; '
                       'vanilla 26.3 chunk_surface_level wrapper continues to reference it.')

new_ns = {
    'sea_level': ns.get('sea_level', 63),
    'disable_mob_generation': ns.get('disable_mob_generation', False),
    'legacy_random_source': ns.get('legacy_random_source', False),
    'noise': {'min_y': ns['noise']['min_y'], 'height': ns['noise']['height']},
    'default_block': 'minecraft:stone',
    'default_fluid': 'minecraft:water',
    'noise_router': {
        'temperature': nr_old['temperature'],
        'vegetation': nr_old['vegetation'],
        'continents': nr_old['continents'],
        'erosion': nr_old['erosion'],
        'depth': nr_old['depth'],
        'ridges': nr_old['ridges'],
        'final_density': nr_old['final_density'],
        'chunk_surface_level': 'minecraft:overworld/chunk_surface_level',
    },
    'spawn_target': ns.get('spawn_target', []),
    'material_rule': 'minecraft:overworld',
}
W(f'{PORT}/data/minecraft/worldgen/noise_settings/overworld.json', new_ns)
note('noise-settings', 'noise_settings/overworld.json rebuilt to the 26.3 schema: aquifer fields moved out of '
                       'noise_router (aquifers object omitted -> aquifers disabled, matching the original pack '
                       'which nulled all aquifer fields), vein_toggle/vein_ridged/vein_gap removed (system replaced '
                       'by 26.3 ore_vein material rules - vanilla 26.3 rules are used because the pack\'s vein '
                       'functions were verbatim copies of vanilla 26.2), default_block/default_fluid as block-id '
                       'strings, noise{min_y,height} only (size_horizontal/size_vertical no longer exist; pack '
                       'used 1/1 which corresponds to the 4x4 interpolation cells set in migrated DFs), '
                       'surface_rule -> material_rule reference.')

# ---------------- 6. material_rule/overworld.json ----------------
sr = ns['surface_rule']
sr_mig = df_migrate(sr, stats)   # runs through harmlessly; surface rules have no DF types, but catches nested surprises
sr_mig = migrate_feature_json(sr_mig, 'material_rule/overworld')   # block states -> strings (26.3)
seq = sr_mig['sequence']
new_seq = [seq[0], 'minecraft:overworld/copper_ore_vein', 'minecraft:overworld/iron_ore_vein'] + seq[1:]
W(f'{PORT}/data/minecraft/worldgen/material_rule/overworld.json', {'type': 'minecraft:sequence', 'sequence': new_seq})
note('material-rule', 'The pack\'s 36KB surface rule is now a named material rule (worldgen/material_rule/overworld.json), '
                      'overriding vanilla\'s. Vanilla 26.3 copper/iron ore_vein rules spliced in right after the '
                      'bedrock gradient entry, mirroring vanilla ordering (bedrock_floor -> ore veins -> surface).')

# ---------------- 6b. canonical climate density functions ----------------
# 26.3 multi_noise biome source resolves climate by canonical DF ids; the pack must provide them.
climate_aliases = {
    'temperature':     'minecraft:biome/overworld/temperature',
    'humidity':        'minecraft:biome/overworld/vegetation',
    'continentalness': 'minecraft:biome/overworld/continentalness_plus',
    'erosion':         'minecraft:biome/overworld/erosion',
    'weirdness':       'minecraft:biome/overworld/ridges_extra',
    'depth':           'minecraft:biome/overworld/depth',
}
for name, ref in climate_aliases.items():
    W(f'{PORT}/data/minecraft/worldgen/density_function/{name}.json',
      {'type': 'minecraft:cache', 'input': ref})
W(f'{PORT}/data/minecraft/worldgen/density_function/offset.json',
  {'type': 'minecraft:cache', 'input': 0})
note('dimension', 'Added canonical climate density functions (temperature, humidity, continentalness, erosion, '
                  'weirdness, depth, offset) as aliases of the pack climate functions - the 26.3 multi_noise '
                  'biome source resolves climate through these ids. humidity/vegetation, weirdness/ridges and '
                  'offset/0 follow the vanilla 1.18+ noise_router conventions the pack was built on.')

# ---------------- 7. dimension_type: 3-way ----------------
dtP = L(f'{PORT}/data/minecraft/dimension_type/overworld.json')
dtV2, dtV3 = L(f'{V2}/minecraft/dimension_type/overworld.json'), L(f'{V3}/minecraft/dimension_type/overworld.json')
R = json.loads(json.dumps(dtV3))
for k in dtP:
    if k == 'attributes':
        pa, v2a = dtP['attributes'], dtV2['attributes']
        ra = json.loads(json.dumps(dtV3.get('attributes', {})))
        for ak in pa:
            if canon(pa[ak]) != canon(v2a.get(ak)):
                ra[ak] = pa[ak]
        R['attributes'] = ra
    elif canon(dtP[k]) != canon(dtV2.get(k)):
        R[k] = dtP[k]
W(f'{PORT}/data/minecraft/dimension_type/overworld.json', R)
note('dimension-type', 'dimension_type/overworld.json rebased on 26.3 vanilla (gains minecraft:gameplay/straw_bed_rule), '
                       'pack deltas (world height 2096, etc.) reapplied.')

# ---------------- 8. dimension: add dappled_forest routing ----------------
dimP = L(f'{PORT}/data/minecraft/dimension/overworld.json')
biomes_list = dimP['generator']['biome_source']['biomes']
have = {e['biome'] for e in biomes_list}
if 'minecraft:dappled_forest' not in have:
    # Route the new 26.3 biome inside the PACK's climate space: clone the pack's forest
    # entry, narrowed to the cooler half of its temperature band. Multi-noise nearest-center
    # matching then splits the pack's forest climate between forest (warmer half) and
    # dappled_forest (cooler half) - both guaranteed to generate, no dead zones.
    forest = next(e for e in biomes_list if e['biome'] == 'minecraft:forest')
    entry = json.loads(json.dumps(forest))
    entry['biome'] = 'minecraft:dappled_forest'
    t = entry['parameters']['temperature']
    if isinstance(t, list):
        mid = (t[0] + t[1]) / 2
        entry['parameters']['temperature'] = [t[0], mid]
        forest['parameters']['temperature'] = [mid, t[1]]
    biomes_list.append(entry)
    W(f'{PORT}/data/minecraft/dimension/overworld.json', dimP)
note('dimension', 'dappled_forest (new in 26.3) routed inside the pack\'s climate space: the pack\'s forest '
                  'temperature band was split in half, with dappled_forest taking the cooler half (nearest-center '
                  'matching gives both biomes stable, adjacent territories). The initial attempt with vanilla 26.3 '
                  'parameter ranges produced no dappled_forest within 6000+ blocks under the pack\'s own '
                  'mid-frequency climate functions, so the pack-native routing above replaced it.')

# ---------------- 9. pack.mcmeta ----------------
mc = L(f'{PORT}/pack.mcmeta')
mc['pack']['description'] = 'JJThunder to the Max v0.9.0 - unofficial Minecraft 26.3 port'
W(f'{PORT}/pack.mcmeta', mc)
note('pack.mcmeta', 'pack_format stays 107 with supported_formats [1,999] (declared by the original author) so the '
                    'pack loads on 26.3 regardless of its format number; description marks the unofficial port.')

# ---------------- verification ----------------
print('=== MIGRATION STATS ===')
for k, v in stats.items(): print(f'  {k}: {v}')

print()
print('=== VERIFY ===')
errors = []

# no dead refs / old syntax anywhere in port
bad_patterns = ['"type": "minecraft:random_offset"', '"type": "minecraft:cache_2d"',
                '"type": "minecraft:flat_cache"', '"type": "minecraft:shifted_noise"',
                '"type": "minecraft:y_clamped_gradient"', '"argument1":', '"argument2":',
                'configured_carver']
for root, _, files in os.walk(f'{PORT}/data'):
    for f in files:
        s = open(os.path.join(root, f)).read()
        for t in bad_patterns:
            if t in s: errors.append(f'{os.path.relpath(root, PORT)}/{f}: contains "{t}"')

# biomes: new format
bdir = f'{PORT}/data/minecraft/worldgen/biome'
for f in sorted(os.listdir(bdir)):
    d = L(f'{bdir}/{f}')
    if 'spawners' in d or 'spawn_costs' in d: errors.append(f'biome/{f}: legacy spawners key')
    if d.get('carvers') != []: errors.append(f'biome/{f}: carvers not empty')
    nms = d.get('attributes', {}).get('minecraft:gameplay/natural_mob_spawns')
    if nms is None: errors.append(f'biome/{f}: no natural_mob_spawns attribute')

# noise_settings schema
nsn = L(f'{PORT}/data/minecraft/worldgen/noise_settings/overworld.json')
expect = {'sea_level', 'disable_mob_generation', 'legacy_random_source', 'noise',
          'default_block', 'default_fluid', 'noise_router', 'spawn_target', 'material_rule'}
extra = set(nsn) - expect
if extra: errors.append(f'noise_settings extra keys: {extra}')
missing = {'temperature', 'vegetation', 'continents', 'erosion', 'depth', 'ridges', 'final_density',
           'chunk_surface_level'} - set(nsn['noise_router'])
if missing: errors.append(f'noise_router missing: {missing}')

# material rule
mr = L(f'{PORT}/data/minecraft/worldgen/material_rule/overworld.json')
if 'minecraft:overworld/copper_ore_vein' not in mr['sequence']: errors.append('material_rule: no copper vein')

# dimension routing
dim = L(f'{PORT}/data/minecraft/dimension/overworld.json')
bios = {e['biome'] for e in dim['generator']['biome_source']['biomes']}
if 'minecraft:dappled_forest' not in bios: errors.append('dimension: dappled_forest missing')
if 'minecraft:sulfur_caves' not in bios: errors.append('dimension: sulfur_caves missing')

# all json parse
for root, _, files in os.walk(PORT):
    for f in files:
        if f.endswith('.json'):
            try: json.load(open(os.path.join(root, f)))
            except Exception as e: errors.append(f'JSON FAIL {os.path.relpath(os.path.join(root,f), PORT)}: {e}')

if STATE_ERRORS:
    for e in STATE_ERRORS: errors.append(f'STATE: {e}')

if errors:
    print(f'ERRORS ({len(errors)}):')
    for e in errors[:30]: print('  !', e)
else:
    print('  ALL CHECKS PASSED')

# ---------------- zip ----------------
zip_path = f'{BASE}/JJThunder_To_The_Max_26.3_v1.0.0-ported.zip'
if os.path.exists(zip_path): os.remove(zip_path)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(PORT):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, PORT))
print(f'ZIP: {zip_path} ({os.path.getsize(zip_path)} bytes)')

# save notes for repo
with open(f'{WORK}/port_notes_raw.md', 'w') as fh:
    cur = None
    for sec, line in NOTES:
        if sec != cur:
            fh.write(f'\n## {sec}\n')
            cur = sec
        fh.write(f'- {line}\n')
print('NOTES saved')
