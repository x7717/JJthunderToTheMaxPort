#!/usr/bin/env python3
"""Regenerate the pack-vs-vanilla-26.3 biome classification report (for repo/verification)."""
import json, os

PACK = '/home/z/my-project/JJthunderToTheMaxPort/work/pack-extracted/data/minecraft/worldgen/biome'
VAN = '/home/z/my-project/JJthunderToTheMaxPort/work/vanilla-26.3/inner/data/minecraft/worldgen/biome'
SPAWN_KEYS = ('attributes', 'spawners', 'spawn_costs')

def van_spawners(b):
    out = {}
    nms = b.get('attributes', {}).get('minecraft:gameplay/natural_mob_spawns')
    if not nms: return out
    for cat, sp in nms['argument'].get('spawns_by_category', {}).items():
        lst = []
        for s in sp:
            c = s['count']
            if isinstance(c, dict):
                lst.append((s['type'], s['weight'], c['min_inclusive'], c['max_inclusive']))
            else:
                lst.append((s['type'], s['weight'], c, c))
        out[cat] = sorted(lst)
    return out

def pack_spawners(b):
    return {cat: sorted((s['type'], s['weight'], s['minCount'], s['maxCount']) for s in sp)
            for cat, sp in b.get('spawners', {}).items()}

def colornorm(v):
    if isinstance(v, int) and not isinstance(v, bool): return f'#{v & 0xFFFFFF:06x}'.lower()
    if isinstance(v, str) and v.startswith('#'): return v.lower()
    return v

def semantic_diff(vb, pb):
    diffs = []
    v = {k: x for k, x in vb.items() if k not in SPAWN_KEYS}
    p = {k: x for k, x in pb.items() if k not in SPAWN_KEYS}
    for k in sorted(set(v) | set(p)):
        a, b2 = v.get(k), p.get(k)
        if k == 'effects' and isinstance(a, dict) and isinstance(b2, dict):
            for ek in sorted(set(a) | set(b2)):
                if colornorm(a.get(ek)) != colornorm(b2.get(ek)):
                    diffs.append(f'effects.{ek}: vanilla={a.get(ek)} | pack={b2.get(ek)}')
        elif a != b2 and not (a is None and b2 == []) and not (a == [] and b2 is None):
            diffs.append(f'{k}: vanilla={json.dumps(a)[:120]} | pack={json.dumps(b2)[:120]}')
    vs, ps = van_spawners(vb), pack_spawners(pb)
    for cat in sorted(set(vs) | set(ps)):
        if vs.get(cat) != ps.get(cat):
            diffs.append(f'spawners.{cat}: differs')
    return diffs

identical, modified, custom = [], [], []
report = []
for f in sorted(f2 for f2 in os.listdir(PACK) if f2.endswith('.json')):
    pb = json.load(open(os.path.join(PACK, f)))
    vp = os.path.join(VAN, f)
    if os.path.exists(vp):
        d = semantic_diff(json.load(open(vp)), pb)
        if not d:
            identical.append(f)
            report.append(f'IDENTICAL      {f}')
        else:
            modified.append(f)
            report.append(f'PACK_MODIFIED  {f}  ({len(d)} real diffs)')
            for line in d: report.append(f'    - {line}')
    else:
        custom.append(f)
        report.append(f'PACK_CUSTOM    {f}')

untouched = sorted(set(os.listdir(VAN)) - set(os.listdir(PACK)))
report.append('')
report.append(f'TOTAL overridden by pack: {len(identical)+len(modified)+len(custom)}')
report.append(f'  identical to vanilla 26.3 : {len(identical)}')
report.append(f'  modified by pack          : {len(modified)}')
report.append(f'  pack-custom               : {len(custom)}')
report.append(f'Vanilla 26.3 biomes not overridden ({len(untouched)}):')
report.append('  ' + ', '.join(t[:-5] for t in untouched))

out = '/home/z/my-project/JJthunderToTheMaxPort/work/biome_compare_report.txt'
with open(out, 'w') as fh: fh.write('\n'.join(report) + '\n')
print(f'written {out}: {len(identical)} identical / {len(modified)} modified / {len(custom)} custom')
