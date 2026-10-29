# JJThunder To The Max — Minecraft 26.3 (unofficial port)

An unofficial port of **[JJThunder To The Max](https://modrinth.com/mod/jjthunder-to-the-max)**
by **[jjthunder001](https://modrinth.com/user/jjthunder001)** to **Minecraft 26.3**.

> **Credit & license notice** — the original datapack is the work of **jjthunder001**
> (471K+ downloads on Modrinth) and is **All Rights Reserved**. This repository hosts a
> community port with full attribution. Nothing here is official; for the original pack
> (up to Minecraft 26.2) use the Modrinth link above and support the author.
> Original version ported: **v0.9.0** (26.2 build).

## What this pack does

JJThunder To The Max replaces the entire overworld generation with an extreme,
"realism"-driven terrain engine: a 2096-block-tall world (min y -64), fully custom
density-function terrain shaping, custom mountain ranges, its own cave system, custom
biomes (**Molten Peaks**, **Underground**, **Deep Underground**) and re-tuned surface
rules for every biome — including sulfur-painted **Sulfur Caves**.

## What the port had to change (26.2 → 26.3)

Minecraft 26.3 changed the worldgen data formats significantly. Every change is
mechanical and documented in [PORT_NOTES_raw.md](PORT_NOTES_raw.md); the ported pack is
content-faithful to v0.9.0 (verified 3-way: pack ↔ vanilla 26.2 ↔ vanilla 26.3):

| Area | 26.2 (original) | 26.3 (this port) |
|------|-----------------|------------------|
| Biome mob spawning | top-level `spawners` / `spawn_costs` | moved into `attributes/minecraft:gameplay/natural_mob_spawns` |
| `creature_spawn_probability` | top-level key | `attributes/minecraft:gameplay/creature_world_gen_spawn_probability` |
| Configured carvers | data-driven registry (`probability: 0` trick to disable carving) | registry removed in 26.3 → carvers disabled via empty biome `carvers` lists instead |
| Configured features | `worldgen/configured_feature/` + `config` envelope | renamed to `worldgen/feature/`, `config` flattened, block states as strings |
| Density functions | `argument1/argument2`, `cache_2d`, `flat_cache`, `shifted_noise`, `y_clamped_gradient` | `left/right`, `cache`, `noise`, `gradient` (+ explicit 4×4 interpolation cells) |
| Noise parameters | `firstOctave` + `amplitudes[]` | `base_octave` + `base_amplitude`/`octave_count`/`amplitude_modifiers` (per-profile normalization constants taken from vanilla 26.3 where profiles match) |
| Surface rules | inline in `noise_settings` | named `material_rule` file (`worldgen/material_rule/overworld.json`), vanilla 26.3 ore-vein rules spliced in |
| Aquifers | disabled via null fields in the router | aquifer object omitted (still disabled) |
| Climate routing | via `noise_router` fields | canonical climate density functions (`temperature`, `humidity`, `continentalness`, `erosion`, `weirdness`, `depth`, `offset`) aliasing the pack's climate functions |
| New in 26.3 | — | **dappled_forest** routed into the pack's forest climate slot (cooler temperature half) so the new biome generates |

Nothing about the pack's terrain design, biome layouts, features, structures or spawn
tables was changed. The only additive tweak is dappled_forest routing (a new vanilla 26.3
biome the original pack could not know about).

## Verification (all logs in [`verification/`](verification/))

1. **`run1`** — official vanilla 26.3 server, fresh world: pack auto-loaded, **0 parse/load errors**,
   `/locate biome minecraft:sulfur_caves` → found 1378 blocks from spawn.
2. **`run2`** — world reload + rare-biome probes from 4 distant corners.
3. **`run3`** — final full pass: sulfur_caves round-trip (biome at the located point resolves
   back to itself, distance 0), pack-custom `underground`/`deep_dark` located, overridden
   mineshafts located 71 blocks from spawn, dappled_forest found (3769 blocks).
   Note: `molten_peaks` needs >6 km spacing by design (continentalness 1.8–2.0 + hot band) —
   identical to the original pack's routing.
4. **`run4`** — Paper 26.3 (build 230) + the bundled **JJVerify** plugin:
   `/jjverify` → **PASS — 52/52 checks** (world bounds -64/2032/63, all 43 biomes registered,
   4 live biome probes exact, mineshaft + stronghold locates within limits).
   Full JSON: [`verification/jjverify-report.json`](verification/jjverify-report.json).

## The JJVerify plugin (`plugin/`)

A small Paper plugin (`/jjverify`, source in `plugin/src`, manifest generated from the
ported pack) that compares the live server against the expected port state:

- world bounds & sea level (the 2096-block-tall dimension),
- presence of every pack biome + `dappled_forest` in the registry,
- live biome probes at coordinates proven during porting,
- live structure locates (mineshaft spacing is part of the pack's override).

Build it with any JDK 25: `javac -cp <paper-api-26.3.jar> plugin/src/dev/jjthunder/port/JJVerifyPlugin.java`
(a prebuilt `JJVerify-1.0.0.jar` is included).

## Installing the datapack

1. Download [`datapack/JJThunder_To_The_Max_26.3_v1.0.0-ported.zip`](datapack/).
2. Drop it into `<world>/datapacks/` **before generating the world** (worldgen datapacks
   must be present at first launch; on an existing world you must delete/regenerate it).
3. Recommended server settings: `view-distance` ≤ 8 — the 2096-block-tall terrain is heavy.
4. Works on vanilla 26.3 and Paper 26.3. Single-player: put it in the resource-pack-style
   datapacks folder of a new world.

## Repository layout

```
datapack/          the ported pack (drop-in zip)
datapack-source/   unpacked pack source (data/ + pack.mcmeta)
plugin/            JJVerify plugin (source, manifest, prebuilt jar)
verification/      all test-run logs + reports (runs 1-4)
tools/             the porting & test scripts used to produce everything above
PORT_NOTES_raw.md  machine-generated list of every transformation applied
ORIGINAL_PACK.md   attribution + links to the original Modrinth project
```

## Credits

- **jjthunder001** — original JJThunder To The Max (all worldgen design)
- Port, format migration and verification tooling — this repository's contributors
