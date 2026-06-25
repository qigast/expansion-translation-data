from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


INVALID_RE = re.compile(r"\[\~ \d+\]")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
UNDERSCORE_RE = re.compile(r"_+")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_lines(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as f:
        return [line.rstrip("\r\n") for line in f]


def apply_rules(value: str, rules: dict[str, Any]) -> str:
    for old, new in rules.get("hasReplace", {}).items():
        value = value.replace(old, new)

    if rules.get("toStrip"):
        value = value.strip()

    return value


def is_valid(value: str) -> bool:
    return bool(value) and not INVALID_RE.fullmatch(value)


def to_constant(value: str, prefix: str | None = None) -> str:
    value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )

    value = NON_ALNUM_RE.sub("_", value)
    value = UNDERSCORE_RE.sub("_", value).strip("_")

    return f"{prefix}{value}" if prefix else value


def should_replace(
    current: str | None,
    candidate: str,
    keep_shortest: bool,
) -> bool:
    if current is None:
        return True

    if keep_shortest:
        return len(candidate) < len(current)

    return False


def process(
    config: dict[str, Any],
    root: Path,
    add_source: bool,
) -> tuple[
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, str]],
]:
    rules = config["rules"]
    schema = config["schema"]

    file_cache: dict[Path, list[str]] = {}
    objects_by_output: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    maps_by_output: dict[str, dict[str, str]] = defaultdict(dict)

    ids_by_source: dict[str, list[str]] = {}
    counts_by_source: dict[str, int] = {}
    source_to_outputs: dict[str, tuple[str, str]] = {}

    def get_lines(relpath: str) -> list[str]:
        path = root / relpath
        if path not in file_cache:
            file_cache[path] = load_lines(path)
        return file_cache[path]

    outputs = [
        (re.compile(pattern), data_file, map_file)
        for pattern, (data_file, map_file) in config["outputs"].items()
    ]

    for source_name, source in schema["name"].items():
        en_lines = get_lines(source["en"])
        fr_lines = get_lines(source["fr"])

        beg = source["beg"]
        end = source["end"]
        prefix = source.get("prefix")

        codes: list[str] = []

        for idx in range(beg, end + 1):
            en_value = apply_rules(en_lines[idx], rules["name"])
            fr_value = apply_rules(fr_lines[idx], rules["name"])

            if not is_valid(en_value) or not is_valid(fr_value):
                continue

            code = to_constant(en_value, prefix)
            codes.append(code)

            for pattern, data_file, map_file in outputs:
                if pattern.fullmatch(source_name):
                    source_to_outputs[source_name] = (data_file, map_file)

                    obj = objects_by_output[data_file].setdefault(
                        code,
                        {"code": code},
                    )

                    if "name" not in obj:
                        obj["name"] = fr_value

                        if add_source:
                            obj.setdefault("source", {})["name"] = source_name

                    maps_by_output[map_file][en_value] = fr_value

                    break

        ids_by_source[source_name] = codes
        counts_by_source[source_name] = len(codes)

    for field_name, field_sources in schema.items():
        if field_name == "name":
            continue

        field_rules = rules[field_name]
        keep_shortest = field_rules.get("keepShortest", False)

        for source_name, source in field_sources.items():
            if source_name not in ids_by_source:
                continue

            fr_lines = get_lines(source["fr"])
            beg = source["beg"]

            data_file, _ = source_to_outputs[source_name]

            for offset in range(counts_by_source[source_name]):
                code = ids_by_source[source_name][offset]

                value = apply_rules(
                    fr_lines[beg + offset],
                    field_rules,
                )

                if not is_valid(value):
                    continue

                for discard in field_rules.get("toDiscard", []):
                    if re.fullmatch(discard, value):
                        value = ""
                        break

                if not value:
                    continue

                obj = objects_by_output[data_file][code]

                if should_replace(
                    obj.get(field_name),
                    value,
                    keep_shortest,
                ):
                    obj[field_name] = value

                    if add_source:
                        obj.setdefault("source", {})[field_name] = source_name

    return objects_by_output, maps_by_output


def write_outputs(
    output_dir: Path,
    objects: dict[str, dict[str, dict[str, Any]]],
    maps: dict[str, dict[str, str]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, data in objects.items():
        with (output_dir / filename).open("w", encoding="utf-8") as f:
            json.dump(
                dict(sorted(data.items())),
                f,
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
            )

    for filename, data in maps.items():
        with (output_dir / filename).open("w", encoding="utf-8") as f:
            json.dump(
                dict(sorted(data.items())),
                f,
                ensure_ascii=False,
                indent=4,
                sort_keys=True,
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--add-source",
        action="store_true",
    )

    args = parser.parse_args()

    config = load_json(args.config)

    root = Path(config["root"]).expanduser()

    objects, maps = process(
        config=config,
        root=root,
        add_source=args.add_source,
    )

    write_outputs(
        output_dir=args.output,
        objects=objects,
        maps=maps,
    )


if __name__ == "__main__":
    main()