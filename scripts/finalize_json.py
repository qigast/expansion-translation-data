#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"\{[^}]+\}|[^\s{}]+|\s+")


FontMap = dict[str, int]


@dataclass(slots=True)
class FieldRule:
    font: str
    column: int
    line: int


@dataclass(slots=True)
class ValidationError:
    entry: str
    field: str
    message: str


@dataclass(slots=True)
class ValidationWarning:
    entry: str
    field: str
    message: str


def load_schema(path: Path) -> dict[str, dict[str, FieldRule]]:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    return {
        pattern: {
            field: FieldRule(**rule)
            for field, rule in fields.items()
        }
        for pattern, fields in raw.items()
    }


def find_rules(
    filename: str,
    schema: dict[str, dict[str, FieldRule]],
) -> dict[str, FieldRule] | None:
    for pattern, rules in schema.items():
        if re.fullmatch(pattern, filename):
            return rules
    return None


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def token_width(
    token: str,
    font: FontMap,
    warnings: list[ValidationWarning],
    entry: str,
    field: str,
) -> int:
    if token.isspace():
        return sum(font.get(" ", 0) for _ in token)

    if token.startswith("{") and token.endswith("}"):
        if token not in font:
            warnings.append(
                ValidationWarning(
                    entry,
                    field,
                    f"unknown macro {token}",
                )
            )
        return font.get(token, 0)

    width = 0

    for char in token:
        if char not in font:
            warnings.append(
                ValidationWarning(
                    entry,
                    field,
                    f"unknown glyph {char!r}",
                )
            )

        width += font.get(char, 0)

    return width


def reflow_text(
    text: str,
    font: FontMap,
    max_columns: int,
    warnings: list[ValidationWarning],
    entry: str,
    field: str,
) -> tuple[str, int, bool]:
    text = " ".join(text.split())

    tokens = tokenize(text)

    lines: list[str] = []
    current_tokens: list[str] = []
    current_width = 0
    overflow = False

    for token in tokens:
        width = token_width(
            token,
            font,
            warnings,
            entry,
            field,
        )

        if width > max_columns:
            overflow = True

        if not current_tokens:
            if token.isspace():
                continue

            current_tokens.append(token)
            current_width = width
            continue

        if current_width + width > max_columns:
            lines.append("".join(current_tokens).rstrip())

            if token.isspace():
                current_tokens = []
                current_width = 0
            else:
                current_tokens = [token]
                current_width = width

            continue

        current_tokens.append(token)
        current_width += width

    if current_tokens:
        lines.append("".join(current_tokens).rstrip())

    return "\n".join(lines), len(lines), overflow


def validate_and_reflow(
    data_path: Path,
    schema: dict[str, dict[str, FieldRule]],
    fonts: dict[str, FontMap],
) -> tuple[dict[str, Any], dict[str, Any]]:
    rules = find_rules(str(data_path), schema)

    if rules is None:
        raise RuntimeError(
            f"no schema rule matches {data_path}"
        )

    data: dict[str, Any] = json.loads(
        data_path.read_text(encoding="utf-8")
    )

    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    for entry_name, entry in data.items():
        if not isinstance(entry, dict):
            continue

        for field_name, rule in rules.items():
            value = entry.get(field_name)

            if not isinstance(value, str):
                continue

            try:
                font = fonts[rule.font]
            except KeyError:
                raise RuntimeError(
                    f"unknown font {rule.font}"
                )

            wrapped_text, line_count, token_overflow = reflow_text(
                value,
                font,
                rule.column,
                warnings,
                entry_name,
                field_name,
            )

            entry[field_name] = wrapped_text

            if token_overflow:
                errors.append(
                    ValidationError(
                        entry_name,
                        field_name,
                        f"contains token wider than {rule.column} pixels",
                    )
                )

            if line_count > rule.line:
                errors.append(
                    ValidationError(
                        entry_name,
                        field_name,
                        f"uses {line_count} lines, maximum is {rule.line}",
                    )
                )

    report = {
        "file": str(data_path),
        "valid": not errors,
        "errors": [
            {
                "entry": e.entry,
                "field": e.field,
                "message": e.message,
            }
            for e in errors
        ],
        "warnings": [
            {
                "entry": w.entry,
                "field": w.field,
                "message": w.message,
            }
            for w in warnings
        ],
    }

    return data, report


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument("schema", type=Path)
    parser.add_argument("fonts", type=Path)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    try:
        schema = load_schema(args.schema)

        fonts: dict[str, FontMap] = json.loads(
            args.fonts.read_text(encoding="utf-8")
        )

        data, report = validate_and_reflow(
            args.input,
            schema,
            fonts,
        )

    except Exception as exc:
        print(
            json.dumps(
                {"error": str(exc)},
                ensure_ascii=False,
                indent=4,
            ),
            file=sys.stderr,
        )
        return 2

    args.output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=4,
        )
    )

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
