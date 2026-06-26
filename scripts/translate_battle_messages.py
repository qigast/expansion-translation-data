import re
import json
import argparse

# -----------------------------
# CONFIG PATTERN
# -----------------------------
STRING_PATTERN = r'(?:_|COMPOUND_STRING)\(\s*(["\'])(.*?)\1\s*\)'

# -----------------------------
# TEMPLATE
# -----------------------------
class Template:
    def __init__(self, template_string: str):
        self.raw_string = template_string
        self.buffers: dict[str, str] = {}
        self._parse_buffers()
        self.compiled_regex = self._build_compiled_regex()

    def _parse_buffers(self):
        i = 0
        while i < len(self.raw_string):
            if self.raw_string[i] == '{':
                end = self.raw_string.find('}', i)
                if end == -1:
                    raise ValueError("Unmatched '{'")

                name = self.raw_string[i + 1:end]
                if name.startswith("B_"):
                    self.buffers.setdefault(name, "")

                i = end + 1
            else:
                i += 1

    def _build_compiled_regex(self):
        placeholder_pattern = r'\{B_[^\}]+\}'
        literal_chunks = re.split(placeholder_pattern, self.raw_string)

        regex = "^"
        for i, chunk in enumerate(literal_chunks):
            if chunk:
                regex += re.escape(chunk)
            if i < len(literal_chunks) - 1:
                regex += r'(.*?)'
        regex += "$"

        return re.compile(regex, flags=re.DOTALL)

    def extract_buffer_values(self, input_string: str) -> bool:
        match = self.compiled_regex.match(input_string)
        if not match:
            return False

        values = list(match.groups())

        for key, value in zip(self.buffers.keys(), values):
            self.buffers[key] = value

        return True

    def set(self, key: str, value: str):
        if key not in self.buffers:
            raise KeyError(f"Unknown buffer: {key}")
        self.buffers[key] = value

    def get(self, key: str) -> str:
        return self.buffers.get(key, "")

    def keys(self):
        return self.buffers.keys()

    def has_buffer(self, key: str) -> bool:
        return key in self.buffers

    def missing_buffers(self):
        return [k for k, v in self.buffers.items() if v == ""]

    def composable(self):
        return all(v != "" for v in self.buffers.values())

    def compose_string(self) -> str:
        out = self.raw_string
        for k, v in self.buffers.items():
            out = out.replace(f"{{{k}}}", v)
        return out


# -----------------------------
# PARSING
# -----------------------------
def parse_from_file(filename: str) -> list[str]:
    pattern = re.compile(STRING_PATTERN)
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    return [m.group(2) for m in pattern.finditer(content)]


def extract_messages(filename: str) -> list[str]:
    pattern = re.compile(r'MESSAGE\("([^"]*)"\)')
    with open(filename, "r", encoding="utf-8") as f:
        return pattern.findall(f.read())


# -----------------------------
# REGEX RULES
# -----------------------------
def load_regex_rules(path: str):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    rules = []
    for pattern, repl in raw.items():
        rules.append((re.compile(pattern), repl))

    return rules


def apply_regex_rules(text: str, rules) -> str:
    for pattern, repl in rules:
        text = pattern.sub(repl, text)
    return text


# -----------------------------
# NAME MAPS
# -----------------------------
def load_name_maps(paths: list[str]) -> dict[str, str]:
    mapping = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            mapping.update(json.load(f))
    return mapping


def apply_name_maps(text: str, mapping: dict[str, str]) -> str:
    for k in sorted(mapping.keys(), key=len, reverse=True):
        text = text.replace(k, mapping[k])
    return text


# -----------------------------
# TEMPLATE MATCHING (FAST PATH)
# -----------------------------
def find_template_index(templates: list[Template], input_string: str):
    best_idx = -1
    best_template = None
    min_len = float("inf")

    for i, original in enumerate(templates):
        t = Template(original.raw_string)

        if t.extract_buffer_values(input_string):
            captured_len = sum(len(v) for v in t.buffers.values())

            if captured_len < min_len:
                min_len = captured_len
                best_idx = i
                best_template = t

            if captured_len == 0:
                break

    return best_idx, best_template


# -----------------------------
# TRANSLATION
# -----------------------------
def translate_message(message, en_templates, fr_templates, name_map, regex_rules):
    idx, en_t = find_template_index(en_templates, message)

    if idx == -1 or en_t is None:
        return False, "No matching template found"

    fr_t = Template(fr_templates[idx].raw_string)

    for key in en_t.keys():
        if fr_t.has_buffer(key):
            fr_t.set(key, en_t.get(key))

    out = fr_t.compose_string()
    out = apply_regex_rules(out, regex_rules)
    out = apply_name_maps(out, name_map)

    return True, out


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--en", required=True)
    parser.add_argument("--fr", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name-maps", nargs="+", required=True)
    parser.add_argument("--regex-config", required=True)

    args = parser.parse_args()

    # IMPORTANT FIX: PRECOMPILE TEMPLATES ONCE
    en_templates = [Template(t) for t in parse_from_file(args.en)]
    fr_templates = [Template(t) for t in parse_from_file(args.fr)]

    if len(en_templates) != len(fr_templates):
        raise RuntimeError(
            f"Template count mismatch: EN={len(en_templates)} FR={len(fr_templates)}"
        )

    name_map = load_name_maps(args.name_maps)
    regex_rules = load_regex_rules(args.regex_config)

    message_pattern = re.compile(
        r'^(?P<prefix>\s*MESSAGE\(")'
        r'(?P<message>(?:\\.|[^"])*)'
        r'(?P<suffix>"\).*)$'
    )

    with open(args.source, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            match = message_pattern.match(line)

            if not match:
                print(line)
                continue

            message = match.group("message")

            success, result = translate_message(
                message,
                en_templates,
                fr_templates,
                name_map,
                regex_rules,
            )

            if success:
                print(
                    f'{match.group("prefix")}'
                    f'{result}'
                    f'{match.group("suffix")}'
                )
            else:
                print(
                    f'{match.group("prefix")}'
                    f'{message}'
                    f'{match.group("suffix")} '
                    f'// ERROR: {result}'
                )