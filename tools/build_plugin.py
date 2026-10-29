#!/usr/bin/env python3
"""Generate verify-manifest.json from the ported pack + run3 verification results, build the plugin jar."""
import json, os, subprocess, shutil

BASE = '/home/z/my-project/JJthunderToTheMaxPort'
PLUG = f'{BASE}/plugin'
JDK = '/home/z/my-project/tools/jdk-25.0.5+8/bin'

# --- manifest from the ported pack ---
bdir = f'{BASE}/pack-26.3/data/minecraft/worldgen/biome'
pack_biomes = sorted('minecraft:' + f[:-5] for f in os.listdir(bdir) if f.endswith('.json'))
sdir = f'{BASE}/pack-26.3/data/minecraft/worldgen/structure'
pack_structures = sorted('minecraft:' + f[:-5] for f in os.listdir(sdir) if f.endswith('.json'))

manifest = {
    'generated_from': 'JJThunder To The Max v0.9.0 -> 26.3 port (v1.0.0)',
    'expected_min_y': -64,            # pack dimension_type min_y
    'expected_max_height': 2032,      # min_y -64 + height 2096 (Bukkit getMaxHeight is exclusive)
    'expected_sea_level': 63,
    'biomes_must_exist': pack_biomes + ['minecraft:dappled_forest'],
    # live locate probes (run3 proved a mineshaft 71 blocks from spawn)
    'structure_probes': [
        {'type': 'MINESHAFT', 'max_blocks': 3000},
        {'type': 'STRONGHOLD', 'max_blocks': 20000},
    ],
    # probes = points proven by run3 (/locate round-trips on the live server)
    'biome_probes': [
        {'x': 1328, 'y': 290, 'z': 368, 'biome': 'minecraft:sulfur_caves'},
        {'x': 1328, 'y': 162, 'z': 368, 'biome': 'minecraft:underground'},
        {'x': 1808, 'y': 162, 'z': 3696, 'biome': 'minecraft:deep_dark'},
        {'x': -1328, 'y': 674, 'z': -2288, 'biome': 'minecraft:dappled_forest'},
    ],
}
os.makedirs(f'{PLUG}/resources', exist_ok=True)
with open(f'{PLUG}/resources/verify-manifest.json', 'w') as f:
    json.dump(manifest, f, indent=1)
print(f'manifest: {len(pack_biomes)} pack biomes + dappled_forest, {len(pack_structures)} structures in pack, structure probes + 4 biome probes')

# --- compile + package ---
build = f'{PLUG}/build'
shutil.rmtree(build, ignore_errors=True)
os.makedirs(f'{build}/classes', exist_ok=True)
CP = f'{PLUG}/libs/' + ':'.join(sorted(
    os.path.basename(f'{PLUG}/libs/{f}') for f in os.listdir(f'{PLUG}/libs') if f.endswith('.jar')))
CP = ':'.join(f'{PLUG}/libs/{f}' for f in sorted(os.listdir(f'{PLUG}/libs')) if f.endswith('.jar'))
subprocess.run([f'{JDK}/javac', '-cp', CP,
                '-d', f'{build}/classes',
                f'{PLUG}/src/dev/jjthunder/port/JJVerifyPlugin.java'], check=True)
shutil.copy(f'{PLUG}/resources/plugin.yml', f'{build}/classes/plugin.yml')
shutil.copy(f'{PLUG}/resources/verify-manifest.json', f'{build}/classes/verify-manifest.json')
jar = f'{BASE}/JJVerify-1.0.0.jar'
if os.path.exists(jar): os.remove(jar)
subprocess.run([f'{JDK}/jar', '--create', '--file', jar, '-C', f'{build}/classes', '.'], check=True)
print('plugin jar:', jar, os.path.getsize(jar), 'bytes')
