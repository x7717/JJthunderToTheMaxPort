#!/usr/bin/env python3
"""Run 2: reload existing world, probe rare biomes from distant points, verify sulfur caves terrain."""
import subprocess, threading, time, os, re, sys

BASE = '/home/z/my-project/JJthunderToTheMaxPort'
SRV = f'{BASE}/test-server'
JDK = '/home/z/my-project/tools/jdk-25.0.5+8/bin/java'
LOG = f'{BASE}/logs/run2-server-reload.log'

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
        log_f.write(line); lines.append(line.rstrip())
threading.Thread(target=reader, daemon=True).start()

def send(cmd):
    tag(f'$ {cmd}')
    proc.stdin.write(cmd + '\n'); proc.stdin.flush()

def wait_for(pattern, timeout, required=True):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for l in lines:
            if re.search(pattern, l): return True
        time.sleep(2)
    tag(f'TIMEOUT /{pattern}/')
    if required: send('stop'); time.sleep(10); sys.exit(1)
    return False

def run_cmd(cmd, settle=8):
    mark = len(lines)
    send(cmd); time.sleep(settle)
    return lines[mark:]

tag('run2: booting EXISTING world (datapack reload test)...')
wait_for(r'Done \(|Done!', 600)
time.sleep(2)

# exact sulfur caves spot from run1
send('execute in minecraft:overworld run tp @p 1328 300 368'); time.sleep(8)
run_cmd('forceload add 80 20 88 28', 60)   # chunks around [1328,368]

# verify terrain actually generated tall at sulfur caves: probe a high column
run_cmd('execute if block 1328 300 368 minecraft:air run say probe: air at y300', 4)
run_cmd('data get entity @p', 3)

# rare-biome probes from distant corners
for x, z in ((1328, 368), (6000, 6000), (-6000, 6000), (6000, -6000), (-6000, -6000)):
    send(f'execute in minecraft:overworld run tp @p {x} 320 {z}'); time.sleep(8)
    run_cmd('locate biome minecraft:molten_peaks', 12)
    run_cmd('locate biome minecraft:dappled_forest', 12)

run_cmd('save-all', 15)
time.sleep(3)
send('stop')
try: proc.wait(timeout=150)
except subprocess.TimeoutExpired: proc.kill()
tag('server stopped')

full = '\n'.join(lines)
errors = [l for l in lines if re.search(r'Failed to (parse|load)|Couldn\'t parse|Exception|ERROR', l, re.I) and 'GlStateManager' not in l]
tag(f'log lines: {len(lines)}; errors: {len(errors)}')
for e in errors[:10]: print('  ', e[:200])
with open(LOG, 'w') as f: f.write(full + '\n')
tag('log saved')
