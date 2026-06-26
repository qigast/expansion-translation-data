#!/usr/bin/env python3

import json
import re
import sys


def parse_widths(path):
    text = open(path, encoding="utf-8").read()

    m = re.search(
        r"gFontLatinGlyphWidths\[\]\s*=\s*\{(.*?)\};",
        text,
        re.S,
    )
    if not m:
        raise RuntimeError("width table not found")

    return [int(n) for n in re.findall(r"\b\d+\b", m.group(1))]


def parse_charmap(path):
    entries = []

    for line in open(path, encoding="utf-8"):
        line = line.split("@", 1)[0].strip()
        if "=" not in line:
            continue

        lhs, rhs = map(str.strip, line.split("=", 1))

        ordinals = [
            int(x, 16)
            for x in re.findall(r"\b[0-9A-F]{2}\b", rhs)
        ]

        if not ordinals:
            continue

        if lhs.startswith("'") and lhs.endswith("'"):
            symbol = lhs[1:-1]
        else:
            symbol = f"{{{lhs}}}"

        entries.append((symbol, ordinals))

    return entries


def main():
    widths = parse_widths(sys.argv[1])
    charmap = parse_charmap(sys.argv[2])

    result = {}

    for symbol, ordinals in charmap:
        width = sum(widths[i] for i in range(ordinals[0], ordinals[-1] + 1))
        result[symbol] = width

    json.dump(
        result,
        sys.stdout,
        ensure_ascii=False,
        indent=4,
        sort_keys=False,
    )
    print()


if __name__ == "__main__":
    main()