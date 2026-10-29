#!/usr/bin/env python3
"""Investigate: noise base_amplitude formula, material_rule block state format, feature dir schema."""
import json, os, math

BASE = '/home/z/my-project/JJthunderToTheMaxPort/work'
V2 = f'{BASE}/vanilla-26.2/inner/data/minecraft/worldgen'
V3 = f'{BASE}/vanilla-26.3/inner/data/minecraft/worldgen'

def L(p): return json.load(open(p))

print('=== 1. noise formula fit ===')
fits = []
mism = 0
for f in sorted(os.listdir(f'{V3}/noise')):
    p3 = f'{V3}/noise/{f}'
    p2 = f'{V2}/noise/{f}'
    if not os.path.exists(p2): continue
    a, b = L(p2), L(p3)
    amps = b['amplitude_modifiers']
    if 'firstOctave' not in a: continue
    ok_oct = a['firstOctave'] == b['base_octave']
    ok_amps = [float(x) for x in a['amplitudes']] == [float(x) for x in amps]
    ok_cnt = b['octave_count'] == len(a['amplitudes'])
    if not (ok_oct and ok_amps and ok_cnt):
        mism += 1
        print(f'  STRUCT MISMATCH {f}: {a} -> {b}')
        continue
    A = a['amplitudes']
    cands = {
        'sum_abs/2': sum(abs(x) for x in A) / 2,
        'sqrt_sum_sq': math.sqrt(sum(x * x for x in A)),
        'sum_abs': sum(abs(x) for x in A),
        'sqrt_sum_sq/2': math.sqrt(sum(x * x for x in A)) / 2,
        'sum_sq': sum(x * x for x in A),
        'max_abs': max(abs(x) for x in A),
    }
    target = b['base_amplitude']
    hit = None
    for name, v in cands.items():
        if abs(v - target) < 1e-9:
            hit = name
    if hit is None:
        # find closest candidate name for diagnostics
        best = min(cands.items(), key=lambda kv: abs(kv[1] - target))
        fits.append((f, A, target, best))
    else:
        fits.append((f, A, target, (hit, cands[hit])))

from collections import Counter
cnt = Counter(name for _, _, _, (name, _) in fits)
print('formula hit counts across noises:', dict(cnt))
print('samples:')
for f, A, target, (name, v) in fits[:8]:
    print(f'  {f}: A={A} target={target:.10f} {name}={v:.10f}')

print()
print('=== 2. material_rule block states (vanilla 26.3 surface.json) ===')
s = L(f'{V3}/material_rule/overworld/surface.json')
ss = json.dumps(s)
i = ss.find('result_state')
print(ss[max(0, i-120):i+150])
i = ss.find('if_true')
print('...')
print(ss[i:i+150])
# any block state objects with Name?
print('has {"Name": pattern:', '{"Name"' in ss)

print()
print('=== 3. configured_feature -> feature: schema diff (large_dripstone) ===')
a = L(f'{V2}/configured_feature/large_dripstone.json')
b = L(f'{V3}/feature/large_dripstone.json')
print('V2 configured_feature/large_dripstone:', json.dumps(a, indent=1)[:400])
print()
print('V3 feature/large_dripstone:', json.dumps(b, indent=1)[:400])
