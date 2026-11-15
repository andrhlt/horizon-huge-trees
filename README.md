# Horizon Huge Trees

This repository contains the converter for a data-only Horizon 26.3 worldgen port of TannyJung’s Tan’s Huge Trees Main Pack 1.8.0. The ZIP contains vanilla block states, NBT structures, and worldgen JSON. Horizon’s existing data loader handles all placement. No native build, Java mod, or custom blocks are required.

## Install and play

Build the ZIP using the instructions below. The converter is public, and the generated pack is for private play.

Use Horizon Nightly 2026-11-13 (9f42064) or a compatible 26.3 build. On **Create New World → Data Packs**, open the pack folder, copy in `tan-huge-trees-horizon-beta.zip`, and enable it before creating the world. To add it to an existing world, put the ZIP in that world’s `datapacks` folder, enable it, then close and reopen the world. Explore newly generated chunks. Vanilla trees are still present, as with the original Tan pack’s default setup.

The port uses Horizon’s data-only jigsaw ground offset and start checks. Use Horizon for this ZIP.

## Scope

- Baked living shapes from all 38 source families, including the three bush and shrub families. Some oversized shapes are scaled down uniformly to fit the generation footprint and ordinary Overworld heights.
- Variant palettes, plus representative leafless and fallen forms. These are static shapes.
- All 66 upstream tree and shrub placement rules, plus canopy trees for pale gardens and windswept hills. Rules for other Java mods’ biomes use vanilla counterparts. Great Redwood uses vanilla wood and leaves.
- The vanilla structure system approximates Tan’s frequency, spacing, and clusters. Waterside rules use the ocean-floor heightmap and reduced density in the intended biomes. They can also appear away from water. Slope and block-level ground checks, cross-tree spacing, and exact seed parity differ from Tan’s Java implementation.
- The pack covers generated trees and shrubs. Tan’s saplings, living-tree interactions, tree decorations, litter, and other nature structures are outside this worldgen port.

The adjacent report lists every rule’s biomes and placement settings, plus scaled templates.

## Rebuild

Python 3.9+ and a prepared Horizon 26.3 resource directory are required to build the pack. Use the Main Pack archive from the pinned upstream commit:

[Download TannyJung’s Main Pack](https://github.com/TannyJungMC/THT-tree_pack/archive/5f86615bade1edf57abc68fac0c1361ea496e331.zip)

```sh
python3 build_pack.py /path/to/main-pack.zip /path/to/prepared/26.3 tan-huge-trees-horizon-beta.zip
```

Tree shapes and palettes are by TannyJung. The generated pack is for private play. Obtain permission before redistributing it. [Tan’s published terms](https://modrinth.com/mod/tans-huge-trees#terms-of-use)
