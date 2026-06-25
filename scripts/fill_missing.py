from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MISSING_RE = re.compile(
    r"^Missing French (?P<field>\w+) for (?P<code>[A-Z0-9_]+)$"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4,
            sort_keys=False,
        )
        f.write("\n")


def build_reverse_name_map(
    provider_name_map: dict[str, str],
) -> dict[str, str]:
    return {
        french: english
        for english, french in provider_name_map.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("missing", type=Path)
    parser.add_argument("target_json", type=Path)
    parser.add_argument("provider_json", type=Path)
    parser.add_argument("target_name_map", type=Path)
    parser.add_argument("provider_name_map", type=Path)

    args = parser.parse_args()

    target = load_json(args.target_json)
    provider = load_json(args.provider_json)

    target_name_map: dict[str, str] = load_json(args.target_name_map)
    provider_name_map: dict[str, str] = load_json(args.provider_name_map)

    reverse_name_map = build_reverse_name_map(provider_name_map)

    fixed = 0
    remaining_lines: list[str] = []

    with args.missing.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")

            match = MISSING_RE.fullmatch(line.strip())
            if match is None:
                remaining_lines.append(line)
                continue

            field = match.group("field")
            code = match.group("code")

            provider_obj = provider.get(code)
            if provider_obj is None:
                remaining_lines.append(line)
                continue

            if field not in provider_obj:
                remaining_lines.append(line)
                continue

            if code not in target:
                target[code] = {"code": code}

            target[code][field] = provider_obj[field]

            if field == "name":
                french_name = provider_obj["name"]

                english_name = reverse_name_map.get(french_name)
                if english_name is None:
                    remaining_lines.append(line)
                    continue

                target_name_map[english_name] = french_name

            fixed += 1

    save_json(args.target_json, target)
    save_json(args.target_name_map, target_name_map)

    with args.missing.open("w", encoding="utf-8") as f:
        for line in remaining_lines:
            f.write(line)
            f.write("\n")

    print(f"Resolved {fixed} missing entries")
    print(f"Remaining {len(remaining_lines)} entries")


if __name__ == "__main__":
    main()