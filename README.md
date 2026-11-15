# Horizon Huge Trees

This repository contains the converter for a data-only Horizon 26.3 worldgen port of TannyJung’s Tan’s Huge Trees Main Pack 1.8.0. The ZIP contains vanilla block states, NBT structures, and worldgen JSON. Horizon’s existing data loader handles all placement. No native build, Java mod, or custom blocks are required.

## Install with Horizon

If you already have `horizon-huge-trees.zip`, you can add it straight to a world. The launcher’s **Build** button is for native mods. Python is only needed to generate the ZIP from source. Use Horizon Nightly 2026-11-13 (9f42064) or a compatible 26.3 build.

- **Existing world.** In the launcher, select the world’s **Data Packs** list and add the ZIP. You can also run `horizon-launcher worlds datapack-add "My World" dist/horizon-huge-trees.zip`. Reopen the world and explore new chunks.
- **New world.** In **Create New World → Data Packs**, open the pack folder, copy in the ZIP, and enable it before creating the world.

The pack uses Horizon’s jigsaw ground offset and start checks. Vanilla trees still generate alongside the giants, as in Tan’s default setup.

Horizon’s online catalog indexes a `datapack` release ZIP. This repository publishes the converter and build inputs. You build the playable ZIP locally with Tan’s archive. [Horizon registry format](https://playhorizon.dev/docs/api/mod-index)

## Build from source

Download [TannyJung’s Main Pack 1.8.0 archive](https://github.com/TannyJungMC/THT-tree_pack/archive/5f86615bade1edf57abc68fac0c1361ea496e331.zip), then run with Python 3.9 or later.

```sh
python3 build_pack.py /path/to/main-pack.zip
```

The build writes `dist/horizon-huge-trees.zip`, with `pack.mcmeta` and `data/` at the archive root. It uses the bundled list of 26.3 biome IDs and the tags referenced by Tan’s spawn rules. Horizon and Rust are unnecessary at build time. The original `build_pack.py <archive> <prepared-26.3-resources> <output.zip>` form can still override the lookup and output path.

## Scope

- Baked living shapes from all 38 source families, including the three bush and shrub families. Some oversized shapes are scaled down uniformly to fit the generation footprint and ordinary Overworld heights.
- Variant palettes, plus representative leafless and fallen forms. These are static shapes.
- All 66 upstream tree and shrub placement rules, plus canopy trees for pale gardens and windswept hills. Rules for other Java mods’ biomes use vanilla counterparts. Great Redwood uses vanilla wood and leaves.
- The vanilla structure system approximates Tan’s frequency, spacing, and clusters. Waterside rules use the ocean-floor heightmap and reduced density in the intended biomes. They can also appear away from water. Slope and block-level ground checks, cross-tree spacing, and exact seed parity differ from Tan’s Java implementation.
- The pack covers generated trees and shrubs. Tan’s saplings, living-tree interactions, tree decorations, litter, and other nature structures are outside this worldgen port.

The adjacent report lists every rule’s biomes and placement settings, plus scaled templates.

Tree shapes and palettes are by TannyJung. The generated pack is for private play. Obtain permission before redistributing it. [Tan’s published terms](https://modrinth.com/mod/tans-huge-trees#terms-of-use)
