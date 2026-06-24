import argparse
import json
import re
from pathlib import Path
from typing import Set, Dict, Any, List

def extract_c_constants(content: str, prefixes: Set[str]) -> Set[str]:
    matches = set(re.findall(r'\b([A-Z_][A-Z0-9_]+)\b', content))
    return {m for m in matches if any(m.startswith(f"{p}_") for p in prefixes)}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--c-constants", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--missing", type=Path, required=True)
    parser.add_argument("--moves", action="store_true")
    args = parser.parse_args()

    with args.data.open("r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    if args.moves:
        to_delete: Set[str] = set()
        to_add: Dict[str, Any] = {}
        for key, val in data.items():
            if key.endswith(("_PHYSICAL", "_SPECIAL")):
                to_delete.add(key)
                if val.get("description") != "Dummy":
                    base_key = key.replace("_PHYSICAL", "").replace("_SPECIAL", "")
                    val["code"] = base_key
                    to_add[base_key] = val
        for key in to_delete:
            data.pop(key, None)
        data.update(to_add)

    json_keys: Set[str] = set(data.keys())
    prefixes: Set[str] = {k.split("_")[0] for k in json_keys if "_" in k}

    c_content: str = args.c_constants.read_text(encoding="utf-8")
    c_keys: Set[str] = extract_c_constants(c_content, prefixes)

    valid_keys: Set[str] = json_keys & c_keys
    sanitized_data: Dict[str, Any] = {k: data[k] for k in valid_keys}

    ordered_data: Dict[str, Any] = dict(
        sorted(sanitized_data.items(), key=lambda item: str(item[1].get("id", "")))
    )

    with args.data.open("w", encoding="utf-8") as f:
        json.dump(ordered_data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    missing_names: Set[str] = set()
    missing_desc: Set[str] = set()

    for key in c_keys:
        if key not in valid_keys:
            missing_names.add(key)
            missing_desc.add(key)
        else:
            if not data[key].get("name"):
                missing_names.add(key)
            if not data[key].get("description"):
                missing_desc.add(key)

    existing_lines: List[str] = []
    if args.missing.exists():
        existing_lines = args.missing.read_text(encoding="utf-8").splitlines()

    final_lines: List[str] = []
    for line in existing_lines:
        match = re.search(r'\b([A-Z_][A-Z0-9_]+)\b', line)
        if match:
            key = match.group(1)
            if any(key.startswith(f"{p}_") for p in prefixes):
                continue
        final_lines.append(line)

    for key in sorted(c_keys):
        if key in missing_names:
            final_lines.append(f"Missing French name for {key}")
        if key in missing_desc:
            final_lines.append(f"Missing French description for {key}")

    if final_lines:
        args.missing.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    elif args.missing.exists():
        args.missing.unlink()

if __name__ == "__main__":
    main()