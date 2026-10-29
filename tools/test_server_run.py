#!/usr/bin/env python3
"""Full test run of the ported pack on an official Minecraft 26.3 server.
- prepares server dir (eula, properties, datapack)
- boots with JDK 25, drives the console via stdin
- runs datapack checks, biome/structure locates, chunk pregeneration
- saves the complete console log for the GitHub repo
"""
import subprocess, threading, time, os, sys, re, shutil

BASE = '/home/z/my-project/JJthunderToTheMaxPort'
SRV = f'{BASE}/test-server'
JDK = '/home/z/my-project/tools/jdk-25.0.5+8/bin/java'
LOG = f'{BASE}/logs/run1-server.log'
ZIP = f'{BASE}/JJThunder_To_The_Max_26.3_v1.0.0-ported.zip'

os.makedirs(f'{SRV}/world/datapacks', exist_ok=True)
os.makedirs(f'{BASE}/logs', exist_ok=True)
with open(f'{SRV}/eula.txt', 'w') as f: f.write('eula=true\n')
shutil.copy(f'{BASE}/server/server-26.3.jar', f'{SRV}/server-26.3.jar')
props = '''online-mode=false
level-seed=JJThunder263Port
enable-rcon=false
view-distance=5
simulation-distance=5
spawn-protection=0
max-tick-time=-1
sync-chunk-writes=false
motd=JJThunder 26.3 port test
'''
with open(f'{SRV}/server.properties', 'w') as f: f.write(props)
shutil.copy(ZIP, f'{SRV}/world/datapacks/jjthunder-26.3-port.zip')

log_f = open(LOG, 'w', buffering=1)
lines = []
def tag(msg):
    line = f'[driver {time.strftime("%H:%M:%S")}] {msg}'
    lines.append(line); print(line); log_f.write(line + '\n')

proc = subprocess.Popen([JDK, '-Xmx2560M', '-jar', 'server-26.3.jar', 'nogui'],
                        cwd=SRV, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, bufsize=1)

def reader():
    for line in proc.stdout:
        log_f.write(line)
        lines.append(line.rstrip())
reader_t = threading.Thread(target=reader, daemon=True)
reader_t.start()

def send(cmd):
    tag(f'$ {cmd}')
    proc.stdin.write(cmd + '\n'); proc.stdin.flush()

def wait_for(pattern, timeout, required=True):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for l in lines:
            if re.search(pattern, l):
                tag(f'MATCHED /{pattern}/ after {int(time.time()-t0)}s')
                return True
        time.sleep(2)
    tag(f'TIMEOUT waiting for /{pattern}/')
    if required:
        send('stop')
        time.sleep(10)
        sys.exit(1)
    return False

def run_cmd(cmd, settle=6):
    mark = len(lines)
    send(cmd)
    time.sleep(settle)
    return lines[mark:]

# --- boot ---
tag('booting server 26.3 with ported pack...')
if not wait_for(r'Done \(|Done!', 600):
    pass
time.sleep(3)

# --- datapack enabled? ---
out = run_cmd('datapack list', 4)
tag('datapack list output captured')

# --- pregen spawn area (modest: 2 cores, tall world) ---
run_cmd('forceload add -32 -32 32 32', 3)

# --- locate key biomes (pack custom + new 26.3 + vanilla caves biomes) ---
for biome in ('minecraft:sulfur_caves', 'minecraft:dappled_forest', 'minecraft:molten_peaks',
              'minecraft:underground', 'minecraft:deep_dark', 'minecraft:plains'):
    run_cmd(f'locate biome {biome}', 10)

# --- locate structures overridden by the pack ---
for st in ('minecraft:mineshaft', 'minecraft:ancient_city', 'minecraft:stronghold'):
    run_cmd(f'locate structure {st}', 10)

# --- tp into sulfur caves if located (forces real chunk gen there) ---
sulfur = None
for l in lines:
    m = re.search(r'sulfur_caves.*?\[(-?\d+), (-?\d+), (-?\d+)\]', l)
    if m: sulfur = m.group(1)
if sulfur:
    tag(f'teleporting to sulfur caves column x={sulfur}')
    run_cmd(f'execute in minecraft:overworld run tp @p {sulfur} 40 0', 2)
    run_cmd('forceload add -16 -16 16 16', 60)
else:
    tag('NO sulfur_caves located within search range - check biome routing!')

# give worldgen time to chew through pregen area
tag('pregen settling (90s)...')
time.sleep(90)

run_cmd('save-all', 20)
time.sleep(5)
out = run_cmd('stop', 3)
try:
    proc.wait(timeout=120)
except subprocess.TimeoutExpired:
    proc.kill()
tag('server stopped')

# --- analyze log ---
full = '\n'.join(lines)
errors = [l for l in lines if re.search(r'Failed to (parse|load)|Couldn\'t parse|Error loading|Exception loading|missing.*registry|Unknown registry element', l, re.I)]
tag(f'log lines: {len(lines)}')
if errors:
    tag(f'LOAD/PARSE ERRORS FOUND: {len(errors)} (first 15):')
    for e in errors[:15]: print('   ', e[:220])
else:
    tag('NO datapack parse/load errors detected in log')

with open(LOG, 'w') as f:
    f.write(full + '\n')
tag(f'full log saved: {LOG}')
