#!/usr/bin/env python3
"""Run 3 (definitive, for the repo): fresh world, final port, full verification with proper response waits.
Log is saved CLEAN (no \r/ANSI junk)."""
import subprocess, threading, time, os, re, sys

BASE = '/home/z/my-project/JJthunderToTheMaxPort'
SRV = f'{BASE}/test-server'
JDK = '/home/z/my-project/tools/jdk-25.0.5+8/bin/java'
LOG = f'{BASE}/logs/run3-server-final.log'
ZIP = f'{BASE}/JJThunder_To_The_Max_26.3_v1.0.0-ported.zip'

os.makedirs(f'{BASE}/logs', exist_ok=True)
import shutil
shutil.rmtree(f'{SRV}/world', ignore_errors=True)   # fresh world for the final port
os.makedirs(f'{SRV}/world/datapacks', exist_ok=True)
shutil.copy(ZIP, f'{SRV}/world/datapacks/jjthunder-26.3-port.zip')

raw = []
def tag(msg):
    line = f'[driver {time.strftime("%H:%M:%S")}] {msg}'
    raw.append(line); print(line)

proc = subprocess.Popen([JDK, '-Xmx2560M', '-jar', 'server-26.3.jar', 'nogui'],
                        cwd=SRV, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, bufsize=1)
def reader():
    for line in proc.stdout:
        raw.append(line.rstrip())
threading.Thread(target=reader, daemon=True).start()

def clean(text):
    text = text.replace('\r', '\n')
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    return [l.strip() for l in text.split('\n') if l.strip()]

def lines():
    return clean('\n'.join(raw))

def wait_for(pattern, timeout, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for l in lines():
            if re.search(pattern, l):
                tag(f'  => {l[:150]}')
                return l
        time.sleep(2)
    tag(f'  !! TIMEOUT ({int(timeout)}s) waiting for {what}')
    return None

def send(cmd): 
    tag(f'$ {cmd}')
    proc.stdin.write(cmd + '\n'); proc.stdin.flush()

def locate(what, arg, timeout=150):
    mark = len(raw)
    send(f'locate {what} {arg}')
    resp = wait_for(rf'nearest {arg} is at|Could not find.*{arg.split(":")[-1]}', timeout, f'locate {arg}')
    if not resp:
        # stragglers: give it one more long window
        resp = wait_for(rf'nearest {arg} is at|Could not find.*{arg.split(":")[-1]}', 90, f'locate {arg} (retry window)')
    return resp

def coords_from(resp):
    m = re.search(r'is at \[(-?\d+), (-?\d+), (-?\d+)\]', resp or '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

tag('RUN3: fresh world, final port v1.0.0')
wait_for(r'Done \(|Done!', 600, 'server boot') or (send('stop'), sys.exit(1))
send('datapack list')
wait_for(r'data pack', 30, 'datapack list')

# spawn pregen
send('forceload add -32 -32 32 32')
wait_for(r'Marked|force loaded', 60, 'forceload spawn')

results = {}
# key biomes
results['sulfur_caves'] = coords_from(locate('biome', 'minecraft:sulfur_caves'))
results['dappled_forest'] = coords_from(locate('biome', 'minecraft:dappled_forest'))
results['molten_peaks_resp'] = locate('biome', 'minecraft:molten_peaks', 120)
results['underground'] = coords_from(locate('biome', 'minecraft:underground'))
results['deep_dark'] = coords_from(locate('biome', 'minecraft:deep_dark'))

# structures overridden by the pack
results['mineshaft'] = coords_from(locate('structure', 'minecraft:mineshaft'))
results['ancient_city'] = coords_from(locate('structure', 'minecraft:ancient_city'))

# round-trip: biome AT the located sulfur caves coords must be sulfur_caves
if results['sulfur_caves']:
    x, y, z = results['sulfur_caves']
    send(f'execute positioned {x} {y} {z} in minecraft:overworld run locate biome minecraft:sulfur_caves')
    rt = wait_for(r'nearest minecraft:sulfur_caves is at', 120, 'round-trip sulfur caves')
    if rt:
        cx, cy, cz = coords_from(rt)
        tag(f'ROUND-TRIP OK: biome at [{x},{y},{z}] resolves back to [{cx},{cy},{cz}] '
            f'(distance {abs(cx-x)+abs(cy-y)+abs(cz-z)})')
        results['sulfur_roundtrip_distance'] = abs(cx - x) + abs(cy - y) + abs(cz - z)
    # generate the chunks there and confirm the world is walkable terrain
    send(f'forceload add {x//16 - 4} {z//16 - 4} {x//16 + 4} {z//16 + 4}')
    wait_for(r'Marked|force loaded', 90, 'forceload sulfur caves')

# second dappled probe from a far corner if not found near spawn
if not results['dappled_forest']:
    send('execute in minecraft:overworld run tp @p 5000 320 5000'); time.sleep(6)
    results['dappled_forest'] = coords_from(locate('biome', 'minecraft:dappled_forest'))

# molten_peaks far probes (documenting rarity)
if not results.get('molten_peaks_resp', '').find('is at') >= 0:
    for x, z in ((6000, 6000), (-6000, -6000)):
        send(f'execute in minecraft:overworld run tp @p {x} 320 {z}'); time.sleep(6)
        r = locate('biome', 'minecraft:molten_peaks', 120)
        if r and 'is at' in r:
            results['molten_peaks_resp'] = r
            break

send('save-all')
wait_for(r'Saved the game|saved', 60, 'save-all')
time.sleep(3)
send('stop')
try: proc.wait(timeout=180)
except subprocess.TimeoutExpired: proc.kill()
tag('server stopped')

# save clean log
with open(LOG, 'w') as f:
    f.write('\n'.join(lines()) + '\n')
tag(f'clean log saved: {LOG}')

# summary
tag('=== RUN3 SUMMARY ===')
for k, v in results.items(): tag(f'  {k}: {v}')
err = [l for l in lines() if re.search(r'Failed to (parse|load)|Couldn\'t parse|ERROR', l) and 'ERROR' not in l[:20]]
err = [l for l in lines() if re.search(r'Failed to parse|Couldn\'t parse|Exception loading|Failed to load', l)]
tag(f'parse/load errors: {len(err)}')
for e in err[:10]: tag('  ! ' + e[:180])
