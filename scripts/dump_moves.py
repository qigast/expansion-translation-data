#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path

INPUT_DIR = Path("api-data/data/api/v2/move")

moves = {}
name_map = {}


def normalize_code(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"MOVE_{name.upper()}"


def normalize_text(text: str) -> str:
    text = (
        text.replace("’", "'")
            .replace("\n", " ")
            .replace("\\n", " ")
    )
    return re.sub(r"\s+", " ", text).strip()


for path in sorted(INPUT_DIR.glob("*/*.json")):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    move_id = data.get("id", path.parent.name)

    en_name = next(
        (
            normalize_text(entry["name"])
            for entry in data.get("names", [])
            if entry["language"]["name"] == "en"
        ),
        None,
    )

    fr_name = next(
        (
            normalize_text(entry["name"])
            for entry in data.get("names", [])
            if entry["language"]["name"] == "fr"
        ),
        None,
    )

    code = normalize_code(data["name"]) if "name" in data else f"MOVE_UNKNOWN_{move_id}"

    if en_name is None:
        print(f"Missing English name for {code}")

    if fr_name is None:
        print(f"Missing French name for {code}")

    fr_flavors = [
        normalize_text(entry["flavor_text"])
        for entry in data.get("flavor_text_entries", [])
        if entry["language"]["name"] == "fr"
    ]

    if not fr_flavors:
        print(f"Missing French description for {code}")

    if en_name is None or fr_name is None:
        continue

    moves[code] = {
        "id": data["id"],
        "code": code,
        "name": fr_name,
        "description": min(fr_flavors, key=len) if fr_flavors else "",
    }

    name_map[en_name] = fr_name

with open("dump/moves/moves.data.json", "w", encoding="utf-8") as f:
    json.dump(moves, f, ensure_ascii=False, indent=4)

with open("dump/moves/move.names.map.json", "w", encoding="utf-8") as f:
    json.dump(name_map, f, ensure_ascii=False, indent=4)