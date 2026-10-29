#!/usr/bin/env python3
"""Schema drift detection: for every pack-overridden file that also exists in
vanilla 26.2 and 26.3, compare V2 vs V3. Equal -> pack file (26.2 style) is
schema-compatible with 26.3. Different -> needs migration."""
import json, os

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
PACK = f'{BASE}/work/pack-extracted' if os.path.isdir(f'{BASE}/work') else f'{BASE}/pack-extracted'
PACK = f'{BASE}/pack-extracted'
V2   = f'{BASE}/vanilla-26.2/inner/data'
V3   = f'{BASE}/vanilla-26.3/inner/data'

def load(p):
    try:
        with open(p) as f: return json.load(f)
    except Exception:
        return None

def canon(o):
    """Canonical form: sort dict keys recursively."""
    if isinstance(o, dict):
        return {k: canon(v) for k, v in sorted(o.items())}
    if isinstance(o, list):
        return [canon(x) for x in o]
    return o

pack_files = []
for root, _, files in os.walk(PACK):
    for f in files:
        if f.endswith(('.json', '.mcmeta')):
            pack_files.append(os.path.relpath(os.path.join(root, f), PACK))

shared, custom, drifted, missing_v2, missing_v3 = [], [], [], [], []
for rel in sorted(pack_files):
    if not rel.endswith('.json'): continue
    # pack rel starts with 'data/'; vanilla dirs already point INTO data/
    vrel = rel[len('data/'):] if rel.startswith('data/') else rel
    p2, p3 = os.path.join(V2, vrel), os.path.join(V3, vrel)
    in2, in3 = os.path.exists(p2), os.path.exists(p3)
    if in2 and in3:
        a, b = load(p2), load(p3)
        if a is None or b is None:
            print(f'PARSE FAIL {rel}')
            continue
        same = canon(a) == canon(b)
        (shared if same else drifted).append(rel)
    elif in3 and not in2:
        missing_v2.append(rel)   # path exists in 26.3 but not 26.2 (unlikely)
    elif in2 and not in3:
        missing_v3.append(rel)   # REMOVED in 26.3 -> pack file referencing it may break
    else:
        custom.append(rel)

print(f'=== PACK-OVERRIDDEN PATHS SHARED WITH VANILLA: {len(shared)+len(drifted)} ===')
print(f'schema-identical 26.2->26.3 (pack file OK as-is): {len(shared)}')
for r in shared: print('   OK ', r)
print()
print(f'DRIFTED 26.2->26.3 (pack file NEEDS MIGRATION): {len(drifted)}')
for r in drifted: print('   DRIFT ', r)
print()
print(f'path removed in 26.3 (pack file may reference dead stuff): {len(missing_v3)}')
for r in missing_v3: print('   REMOVED ', r)
print()
print(f'pack-custom paths (no vanilla counterpart): {len(custom)}')
for r in custom: print('   CUSTOM ', r)

json.dump({'ok': shared, 'drifted': drifted, 'removed_in_263': missing_v3, 'custom': custom},
          open(f'{BASE}/drift_report.json', 'w'), indent=1)
