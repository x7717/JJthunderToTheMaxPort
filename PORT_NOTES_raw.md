
## overview
- Copied all 279 pack files as base; every vanilla-shared file that was schema-identical in 26.2/26.3 (structures, structure sets, tag, most placed features) is kept as-is.

## carvers
- Removed configured_carver/{cave,cave_extra_underground,canyon}.json - the worldgen/configured_carver registry no longer exists in 26.3 (carvers are code-built-in). The original pack disabled vanilla carving via probability:0 in those files; the same result is preserved by emptying the carvers list in every ported biome.

## placed-features
- 14 placed features migrated: placement modifier "minecraft:random_offset"{xz_spread,y_spread} renamed to "minecraft:offset"{x,y,z} (x=z=old xz_spread, y=old y_spread) per 26.3 vanilla files.

## features
- Renamed registry directory worldgen/configured_feature -> worldgen/feature (26.3 rename; the old directory is silently ignored, which left the pack custom features (frozen_delta_deepslate, frozen_delta_tuff, water_delta) unbound). 5 feature files migrated: the config envelope is flattened to top level and block states are written as block-id strings (validated against the official 26.3 blocks report).

## noise
- 5 noise parameter sets migrated to the 26.3 schema (firstOctave/amplitudes -> base_octave/base_amplitude/octave_count/amplitude_modifiers). base_amplitude is Mojang per-profile normalization constant; exact values were taken from the 26.3 vanilla noise set, because every pack noise profile is either a verbatim vanilla profile (erosion_med == erosion, temperature_med == temperature, vegetation_med == vegetation) or collapses to one (cave -> [1,1], island -> [1]; trailing zero amplitudes are ignored by the normalization).

## density-functions
- 128 of 170 density function files syntax-migrated to 26.3: argument1/argument2 -> left/right; unary .argument -> .input; cache_2d/flat_cache -> cache; shifted_noise -> noise (shift_y dropped, it was ignored by 26.2 as well); y_clamped_gradient -> gradient(axis=y); interpolated gains explicit cell sizes 4x4 (original pack used noise size_horizontal=1/size_vertical=1, i.e. 4x4 blocks per cell).

## biomes
- All 42 biome files migrated to the 26.3 format (mob spawning moved from top-level spawners/spawn_costs to attributes/minecraft:gameplay/natural_mob_spawns; creature_spawn_probability -> attributes/minecraft:gameplay/creature_world_gen_spawn_probability). 0 were content-identical to vanilla (kept 26.3 vanilla content), 37 had pack spawn overrides reapplied, 5 are pack-custom biomes. Author intent (temperature, colors, features, spawn weights) verified against vanilla 26.2 and reapplied only where the pack actually differed from it.
- carvers set to [] in every ported biome (see carvers note).

## noise-settings
- Pack's modified preliminary_surface_level (retuned for the 2096-block tall world) migrated and written to density_function/overworld/preliminary_surface_level.json; vanilla 26.3 chunk_surface_level wrapper continues to reference it.
- noise_settings/overworld.json rebuilt to the 26.3 schema: aquifer fields moved out of noise_router (aquifers object omitted -> aquifers disabled, matching the original pack which nulled all aquifer fields), vein_toggle/vein_ridged/vein_gap removed (system replaced by 26.3 ore_vein material rules - vanilla 26.3 rules are used because the pack's vein functions were verbatim copies of vanilla 26.2), default_block/default_fluid as block-id strings, noise{min_y,height} only (size_horizontal/size_vertical no longer exist; pack used 1/1 which corresponds to the 4x4 interpolation cells set in migrated DFs), surface_rule -> material_rule reference.

## material-rule
- The pack's 36KB surface rule is now a named material rule (worldgen/material_rule/overworld.json), overriding vanilla's. Vanilla 26.3 copper/iron ore_vein rules spliced in right after the bedrock gradient entry, mirroring vanilla ordering (bedrock_floor -> ore veins -> surface).

## dimension
- Added canonical climate density functions (temperature, humidity, continentalness, erosion, weirdness, depth, offset) as aliases of the pack climate functions - the 26.3 multi_noise biome source resolves climate through these ids. humidity/vegetation, weirdness/ridges and offset/0 follow the vanilla 1.18+ noise_router conventions the pack was built on.

## dimension-type
- dimension_type/overworld.json rebased on 26.3 vanilla (gains minecraft:gameplay/straw_bed_rule), pack deltas (world height 2096, etc.) reapplied.

## dimension
- dappled_forest (new in 26.3) routed inside the pack's climate space: the pack's forest temperature band was split in half, with dappled_forest taking the cooler half (nearest-center matching gives both biomes stable, adjacent territories). The initial attempt with vanilla 26.3 parameter ranges produced no dappled_forest within 6000+ blocks under the pack's own mid-frequency climate functions, so the pack-native routing above replaced it.

## pack.mcmeta
- pack_format stays 107 with supported_formats [1,999] (declared by the original author) so the pack loads on 26.3 regardless of its format number; description marks the unofficial port.
