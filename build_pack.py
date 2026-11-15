#!/usr/bin/env python3
"""Convert the Tan's Huge Trees 1.8.0 Main Pack to Horizon 26.3 worldgen."""
import argparse
from collections import defaultdict
import gzip
from io import BytesIO
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import zlib

NS = "tan_trees"
ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "dist" / "horizon-huge-trees.zip"
DATA_VERSION = 5023
RADIUS = 120
TOP = 229  # Leaves headroom on ordinary terrain. Taller trees scale offline.
ROOT_DEPTH = 105

# Vanilla homes for upstream rules that otherwise require another Java mod.
MOD_BIOMES = {
    "biomesoplenty:lush_desert": ("desert",),
    "biomesoplenty:pasture": ("plains", "sunflower_plains"),
    "biomesoplenty:redwood_forest": ("old_growth_spruce_taiga",),
    "regions_unexplored:baobab_savanna": ("savanna", "savanna_plateau"),
    "regions_unexplored:deciduous_forest": ("flower_forest", "dappled_forest", "windswept_forest"),
    "regions_unexplored:joshua_desert": ("desert",),
    "regions_unexplored:barley_fields": ("plains", "sunflower_plains"),
    "regions_unexplored:redwoods": ("old_growth_spruce_taiga",),
    "regions_unexplored:sparse_redwoods": ("old_growth_pine_taiga",),
}
COMMON_BIOMES = {
    "is_plains": ("plains", "sunflower_plains"),
    "is_desert": ("desert",),
    "is_swamp": ("swamp", "mangrove_swamp"),
    "is_dry": ("desert", "badlands", "eroded_badlands", "wooded_badlands",
               "savanna", "savanna_plateau", "windswept_savanna"),
}
# Surface tree biomes added or left to general understory by the source rules.
EXTRA_BIOMES = {
    "pale_garden": ("vanilla/halcyon", ("pale_garden",)),
    "windswept": ("vanilla/aider", ("windswept_hills", "windswept_gravelly_hills")),
}
REDWOOD_BLOCKS = {
    "redwood_wood": "stripped_acacia_wood",
    "stripped_redwood_wood": "stripped_spruce_wood",
    "redwood_leaves": "spruce_leaves",
}


def config(data):
    return dict(re.findall(r"^([a-z_]+)\s*=\s*(.*?)\s*$", data, re.MULTILINE))


def state_parts(state):
    name, _, prop_text = state.partition("[")
    namespace, block = name.split(":")
    if namespace != "minecraft":
        block = REDWOOD_BLOCKS[block]
    props = dict(part.split("=") for part in prop_text.rstrip("]").split(",")) if prop_text else {}
    return "minecraft:" + block, props


def palette(data):
    return {
        int(part): state_parts(value)
        for part, value in re.findall(r"^Block\s+\S+\s+(\d+)\s*=\s*(\S+)", data, re.MULTILINE)
        if value != "none"
    }


def biome_lookup(resources):
    if resources is None:
        data = json.loads((ROOT / "biomes-26.3.json").read_text())
        biomes, tags = set(data["biomes"]), data["tags"]
    else:
        worldgen = resources / "worldgen"
        biomes = set(json.loads((worldgen / "biomes.json").read_text()))
        tags = {
            name: json.loads(value)["values"]
            for name, value in json.loads((worldgen / "biome_tags.json").read_text()).items()
        }

    def lookup(ref):
        if not ref.startswith("#"):
            names = MOD_BIOMES.get(ref)
            if names:
                return {"minecraft:" + name for name in names}
            if ref not in biomes:
                raise ValueError(f"unknown biome {ref}")
            return {ref}
        ns, name = ref[1:].split(":")
        if ns != "minecraft":
            if name == "is_coniferous":
                name = "is_taiga"
            if name in COMMON_BIOMES:
                return {"minecraft:" + name for name in COMMON_BIOMES[name]}
        values = tags[f"minecraft:{name}"]
        return set().union(*(lookup(v if isinstance(v, str) else v["id"]) for v in values))

    def expression(text):
        result = set()
        for alternative in text.split(" / "):
            first, *tests = alternative.split(", ")
            matched = lookup(first)
            for test in tests:
                if test.startswith("!"):
                    matched -= lookup(test[1:])
                else:
                    matched &= lookup(test)
            result.update(matched)
        return sorted(result)

    return expression


def bounds(points):
    return tuple((min(axis), max(axis)) for axis in zip(*points))


def shape_points(raw, materials, form):
    if len(raw) < 36 or (len(raw) - 36) % 8:
        raise ValueError("Invalid Tan shape record length")
    shape = {}
    for part, x, y, z in struct.iter_unpack(">4h", memoryview(raw)[36:]):
        if part not in materials:
            continue
        if form != "living" and 1200 <= part < 1210:
            continue
        if form == "fallen":
            x, y = y, -x
        # Prefer wood over foliage where downsampling combines several blocks.
        rank = 0 if 1200 <= part < 1210 else 1
        shape[x, y, z] = (rank, part)
    if not shape:
        raise ValueError("No mapped blocks in shape")
    return shape


def fit(points, start_height, form):
    (min_x, max_x), (min_y, max_y), (min_z, max_z) = bounds(points)
    if form == "fallen":
        lift = -min_y + min(3, (max_y - min_y) // 4)
        points = {(x, y + lift, z): part for (x, y, z), part in points.items()}
        min_y += lift
        max_y += lift
    center_x, center_z = (min_x + max_x) // 2, (min_z + max_z) // 2
    scale = min(1, RADIUS / max(1, max_x - center_x, max_z - center_z),
                TOP / max(1, max_y + start_height),
                ROOT_DEPTH / max(1, -min_y - start_height))
    fitted = {}
    for (x, y, z), value in points.items():
        pos = (round((x - center_x) * scale), round(y * scale), round((z - center_z) * scale))
        if pos not in fitted or value[0] >= fitted[pos][0]:
            fitted[pos] = value
    return fitted, scale


def nbt_string(text):
    raw = text.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def nbt_tag(kind, name, value):
    return bytes((kind,)) + nbt_string(name) + value


def nbt_list(name, kind, items):
    return nbt_tag(9, name, struct.pack(">Bi", kind, len(items)) + b"".join(items))


def nbt_ints(name, values):
    return nbt_list(name, 3, [struct.pack(">i", n) for n in values])


def nbt_state(state):
    name, props = state
    data = nbt_tag(8, "Name", nbt_string(name))
    if props:
        data += nbt_tag(10, "Properties",
                        b"".join(nbt_tag(8, k, nbt_string(v)) for k, v in props.items()) + b"\0")
    return data + b"\0"


def template(points, materials):
    (min_x, max_x), (min_y, max_y), (min_z, max_z) = bounds(points)
    max_y = max(max_y, 0)
    # Symmetric template bounds make the start's sampled surface column its pivot.
    rx, rz = max(-min_x, max_x), max(-min_z, max_z)
    # Horizon's per-pool-element ground level must be nonnegative. Preserve
    # blank space from the shape's origin down to the lowest present block.
    min_y = min(min_y, 0)
    pivot = points.pop((0, min_y, 0), None)
    final_state = "minecraft:structure_void"
    if pivot:
        name, props = materials[pivot[1]]
        final_state = name + ("[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]" if props else "")
    parts = sorted({part for _, part in points.values()})
    indices = {part: i for i, part in enumerate(parts)}
    result = BytesIO()
    result.write(b"\x0a\x00\x00")
    result.write(nbt_tag(3, "DataVersion", struct.pack(">i", DATA_VERSION)))
    result.write(nbt_ints("size", (2 * rx + 1, max_y - min_y + 1, 2 * rz + 1)))
    states = [nbt_state(materials[p]) for p in parts]
    states.append(nbt_state(("minecraft:jigsaw", {"orientation": "north_up"})))
    result.write(nbt_list("palette", 10, states))
    result.write(nbt_list("entities", 10, []))
    result.write(b"\x09" + nbt_string("blocks") + struct.pack(">Bi", 10, len(points) + 1))
    block = struct.Struct(">iii")
    index = struct.Struct(">i")
    # Vanilla stores shape blocks by height; put solid blocks in first.
    ordered = sorted(points.items(), key=lambda pair: (-pair[1][0], pair[0][1], pair[0][0], pair[0][2]))
    for (x, y, z), (_, part) in ordered:
        result.write(b"\x09\x00\x03pos\x03\x00\x00\x00\x03" +
                     block.pack(x + rx, y - min_y, z + rz) +
                     b"\x03\x00\x05state" + index.pack(indices[part]) + b"\x00")
    result.write(nbt_ints("pos", (rx, 0, rz)))
    result.write(nbt_tag(3, "state", index.pack(len(parts))))
    jigsaw = {"id": "minecraft:jigsaw", "name": f"{NS}:pivot", "target": "minecraft:empty",
              "pool": "minecraft:empty", "joint": "rollable", "final_state": final_state}
    result.write(nbt_tag(10, "nbt", b"".join(nbt_tag(8, k, nbt_string(v)) for k, v in jigsaw.items()) + b"\0"))
    result.write(b"\0\0")
    return gzip.compress(result.getvalue(), compresslevel=4, mtime=0), -min_y, max_y


def write_json(out, path, obj):
    out.writestr(path, json.dumps(obj, separators=(",", ":")) + "\n")


def rules(files, biomes):
    matches = {}
    for path, data in sorted(files.items()):
        if not path.startswith("world_gen/") or not path.endswith(".txt") or "/nature_stuffs/" in path:
            continue
        rule = config(data.decode("utf-8-sig"))
        if rule["enable"] != "true":
            continue
        name = path.removeprefix("world_gen/").removesuffix(".txt").replace("#", "")
        rule["biomes"] = biomes(rule["biome"])
        matches[name] = rule
    for name, (source, names) in EXTRA_BIOMES.items():
        matches["horizon/" + name] = matches[source] | {
            "biomes": ["minecraft:" + biome for biome in names], "rarity": "25"
        }
    return matches


def pack_files(archive):
    with ZipFile(archive) as source:
        files = {}
        for ref in source.infolist():
            path = PurePosixPath(ref.filename)
            if len(path.parts) < 3 or ref.is_dir():
                continue
            relative = "/".join(path.parts[1:])
            if relative.startswith("world_gen/") or (relative.startswith("presets/") and
                    (relative.endswith("_settings.txt") or re.fullmatch(r"presets/[^/]+/storage/[^/]+\.bin", relative))):
                files[relative] = source.read(ref)
        return files


def location(value):
    return value.replace("presets/#main/", "presets/", 1)


def resource(path):
    return f"data/{NS}/{path}"


def build(archive, resources, output):
    files = pack_files(archive)
    spawn_rules = rules(files, biome_lookup(resources))
    by_storage = defaultdict(list)
    for filename in sorted(files):
        if filename.endswith(".bin"):
            by_storage[filename.rsplit("/", 1)[0]].append(filename)

    counts = {"source_shapes": sum(map(len, by_storage.values())), "families": [], "rules": {},
              "scaled_shapes": [], "templates": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp")
    templates = {}
    coverage = set()
    try:
        with ZipFile(temp, "w", ZIP_DEFLATED, compresslevel=4) as out:
            out.write(ROOT / "pack.mcmeta", "pack.mcmeta")
            for name, rule in spawn_rules.items():
                storage = location(rule["path_storage"])
                family = storage.split("/")[1]
                settings_path = location(rule["path_settings"]) + ".txt"
                settings = files[settings_path].decode("utf-8-sig")
                settings_name = settings_path.removeprefix("presets/").removesuffix("_settings.txt").replace("#", "")
                start_height = int(config(settings).get("start_height", 0))
                shoreline = rule["spawn_type"] == "waterside"
                # Emergent species keep their upstream placement height.
                heights = "OCEAN_FLOOR_WG" if shoreline or family in {"mangrove", "whisper"} else "WORLD_SURFACE_WG"
                chance = float(rule["dead_tree_chance"])
                key = (family, settings_name)
                if key not in templates:
                    variants = []
                    packed = palette(settings)
                    sources = by_storage[storage]
                    for i, filename in enumerate(sources):
                        forms = ["living"]
                        if i == 0:
                            forms.append("bare")
                        if i == 1 or (i == 0 and len(sources) == 1):
                            forms.append("fallen")
                        for form in forms:
                            points = shape_points(files[filename], packed, form)
                            fitted, scale = fit(points, start_height, form)
                            nbt, depth, top = template(fitted, packed)
                            stem = f"trees/{settings_name}/{i:02d}_{form}"
                            out.writestr(resource(f"structure/{stem}.nbt"), nbt, compress_type=ZIP_STORED)
                            variants.append((stem, depth, top, form))
                            if scale < 1 and form == "living":
                                counts["scaled_shapes"].append({"template": stem, "scale": round(scale, 4)})
                    templates[key] = variants
                    counts["templates"] += len(variants)

                # Horizon stores the ground offset per template, so variants of
                # unequal root depth can share a pool and still sit on the terrain.
                variants = templates[key]
                live_count = sum(v[3] == "living" for v in variants)
                dead_count = len(variants) - live_count
                elements = []
                for stem, depth, _, form in variants:
                    if chance == 1 and form == "living":
                        continue
                    if chance == 0 and form != "living":
                        continue
                    weight = max(1, round(10 * (1 - chance))) if form == "living" else max(
                        1, round(10 * live_count * chance / dead_count))
                    elements.append({"weight": min(150, weight), "element": {
                        "element_type": "minecraft:single_pool_element", "projection": "rigid",
                        "location": f"{NS}:{stem}", "processors": "minecraft:empty",
                        "horizon:ground_level": depth,
                    }})
                write_json(out, resource(f"worldgen/template_pool/{name}.json"), {
                    "fallback": "minecraft:empty", "elements": elements,
                })
                write_json(out, resource(f"tags/worldgen/biome/{name}.json"), {"values": rule["biomes"]})
                structure = {
                    "type": "minecraft:jigsaw", "start_pool": f"{NS}:{name}", "start_jigsaw_name": f"{NS}:pivot", "size": 1,
                    "biomes": f"#{NS}:{name}", "step": "vegetal_decoration",
                    "start_height": {"absolute": start_height}, "project_start_to_heightmap": heights,
                    "max_distance_from_center": 128, "use_expansion_hack": False, "spawn_overrides": {},
                    "terrain_adaptation": "none", "dimension_padding": {"bottom": 1, "top": 1},
                }
                if heights == "WORLD_SURFACE_WG":
                    structure["horizon:start_checks"] = {"liquid": "top"}
                write_json(out, resource(f"worldgen/structure/{name}.json"), structure)
                spacing = max(1, math.ceil(int(rule["min_distance"]) / 16))
                group_low, group_high = (int(v) for v in rule["group_size"].split(" <> "))
                density = float(rule["rarity"]) / 100 * math.sqrt((group_low + group_high) / 2)
                if shoreline:
                    density *= 0.10
                if "degradation" in name:
                    density *= 0.10
                frequency = min(1, density * spacing ** 2)
                placement = {"type": "minecraft:random_spread", "spacing": spacing,
                             "separation": min(spacing - 1, spacing // 2),
                             "salt": zlib.crc32(name.encode()) & 0x7fffffff, "frequency": frequency}
                write_json(out, resource(f"worldgen/structure_set/{name}.json"), {
                    "structures": [{"structure": f"{NS}:{name}", "weight": 1}], "placement": placement,
                })
                counts["rules"][name] = {"family": family, "biomes": rule["biomes"],
                                         "spacing": spacing, "frequency": frequency}
                coverage.update(rule["biomes"])
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    counts["families"] = sorted({r["family"] for r in counts["rules"].values()})
    counts["biomes"] = sorted(coverage)
    output.with_suffix(".report.json").write_text(json.dumps(counts, indent=2) + "\n")
    print(f"{counts['templates']} templates, {len(spawn_rules)} placement rules, "
          f"{len(counts['families'])} families, {len(coverage)} vanilla biomes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Unmodified Tan's Huge Trees Main Pack 1.8.0 archive")
    parser.add_argument("resources", type=Path, nargs="?", help="Override the bundled biome lookup with prepared Horizon 26.3 resources")
    parser.add_argument("output", type=Path, nargs="?", default=DEFAULT_OUTPUT, help="Output ZIP when supplying a resources directory")
    args = parser.parse_args()
    build(args.source, args.resources, args.output)
