from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MISSING_RE = re.compile(
    r"^Missing French (?P<field>\w+) for (?P<code>[A-Z0-9_]+)$"
)

ITEM_RE = re.compile(
    r"\[(?P<code>[A-Z0-9_]+)\]\s*=\s*\{(?P<body>.*?)\n\s*\},",
    re.DOTALL,
)

NAME_RE = re.compile(
    r'\.name\s*=\s*_\("(?P<name>.*?)"\)',
    re.DOTALL,
)

DESCRIPTION_REF_RE = re.compile(
    r"\.description\s*=\s*(?P<symbol>\w+)"
)

DESCRIPTION_RE = re.compile(
    r"static\s+const\s+u8\s+(?P<symbol>\w+)\[\]\s*=\s*_\(\s*(?P<body>.*?)\s*\);",
    re.DOTALL,
)

STRING_RE = re.compile(
    r'"((?:\\.|[^"])*)"'
)

TOKEN_RE = re.compile(
    r"[A-ZÀ-ÖØ-Þ]+(?:[éÉ])[A-ZÀ-ÖØ-Þ]*|[A-ZÀ-ÖØ-Þ]{2,}"
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


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        return load_json(path)

    return {
        "words": {},
        "whitelist": [
            "CT",
            "CS",
        ],
    }


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    save_json(path, cache)


def auto_decap(token: str) -> str:
    return token[:1].upper() + token[1:].lower()


def decap_text(
    text: str,
    cache: dict[str, Any],
) -> str:
    words: dict[str, str] = cache["words"]
    whitelist = set(cache["whitelist"])

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)

        if token in whitelist:
            return token

        if token in words:
            return words[token]

        suggestion = auto_decap(token)

        print()
        print(f"Original : {token}")
        print(f"Suggested: {suggestion}")

        replacement = input("Replacement [Enter to accept]: ").strip()
        final = replacement or suggestion

        words[token] = final
        return final

    return TOKEN_RE.sub(replace, text)


def parse_descriptions(
    content: str,
) -> dict[str, str]:
    descriptions: dict[str, str] = {}

    for match in DESCRIPTION_RE.finditer(content):
        symbol = match.group("symbol")
        body = match.group("body")

        parts = STRING_RE.findall(body)

        text = "".join(parts)
        text = text.replace("\\n", " ")
        text = re.sub(r"\s+", " ", text).strip()

        descriptions[symbol] = text

    return descriptions


def parse_items(
    content: str,
) -> dict[str, dict[str, str]]:
    descriptions = parse_descriptions(content)

    items: dict[str, dict[str, str]] = {}

    for match in ITEM_RE.finditer(content):
        code = match.group("code")
        body = match.group("body")

        name_match = NAME_RE.search(body)
        if name_match is None:
            continue

        desc_match = DESCRIPTION_REF_RE.search(body)
        if desc_match is None:
            continue

        symbol = desc_match.group("symbol")

        if symbol not in descriptions:
            raise RuntimeError(
                f"Could not find description symbol '{symbol}' for {code}"
            )

        items[code] = {
            "name": name_match.group("name"),
            "description": descriptions[symbol],
        }

    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("missing", type=Path)
    parser.add_argument("target_json", type=Path)
    parser.add_argument("items_c", type=Path)
    parser.add_argument("decap_cache", type=Path)

    args = parser.parse_args()

    target = load_json(args.target_json)

    cache = load_cache(args.decap_cache)

    content = args.items_c.read_text(encoding="utf-8")
    items = parse_items(content)

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

            item = items.get(code)
            if item is None:
                remaining_lines.append(line)
                continue

            if field not in item:
                remaining_lines.append(line)
                continue

            value = decap_text(item[field], cache)

            obj = target.setdefault(
                code,
                {"code": code},
            )

            if field == "name":
                obj["name"] = value
                fixed += 1
                continue

            if field == "description":
                if obj.get("description"):
                    remaining_lines.append(line)
                    continue

                obj["description"] = value
                fixed += 1
                continue

            remaining_lines.append(line)

    save_json(args.target_json, target)

    with args.missing.open("w", encoding="utf-8") as f:
        for line in remaining_lines:
            f.write(line)
            f.write("\n")

    save_cache(args.decap_cache, cache)

    print(f"Resolved {fixed} missing entries")
    print(f"Remaining {len(remaining_lines)} entries")


if __name__ == "__main__":
    main()