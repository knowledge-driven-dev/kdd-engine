"""Content parsers for different file formats.

Each parser converts raw content into a list of (heading_path, section_content) tuples,
which is the format consumed by chunking strategies.
"""

import json
import re
from collections.abc import Callable

import yaml

Sections = list[tuple[list[str], str]]

_PARSER_REGISTRY: dict[str, Callable[[str], Sections]] = {}


def register_parser(name: str) -> Callable:
    """Decorator to register a parser function."""

    def decorator(fn: Callable[[str], Sections]) -> Callable[[str], Sections]:
        _PARSER_REGISTRY[name] = fn
        return fn

    return decorator


def get_parser(name: str) -> Callable[[str], Sections]:
    """Get a parser by name.

    Raises ValueError if the parser name is unknown.
    """
    if name not in _PARSER_REGISTRY:
        raise ValueError(
            f"Unknown parser: {name!r}. Available: {sorted(_PARSER_REGISTRY)}"
        )
    return _PARSER_REGISTRY[name]


@register_parser("markdown")
def parse_markdown(content: str) -> Sections:
    """Parse markdown content into sections with heading paths.

    Extracted from ChunkerFactory._parse_sections().
    """
    sections: Sections = []
    current_path: list[str] = []
    current_content: list[str] = []
    current_levels: list[int] = []

    lines = content.split("\n")

    for line in lines:
        if line.startswith("#"):
            section_text = "\n".join(current_content).strip()
            if section_text:
                sections.append((list(current_path), section_text))
            current_content = []

            level = len(line) - len(line.lstrip("#"))
            heading_text = line.lstrip("#").strip()

            while current_levels and current_levels[-1] >= level:
                current_levels.pop()
                if current_path:
                    current_path.pop()

            current_path.append(heading_text)
            current_levels.append(level)
        else:
            current_content.append(line)

    section_text = "\n".join(current_content).strip()
    if section_text:
        sections.append((list(current_path), section_text))

    return sections


def _flatten_json(data: object, path: list[str] | None = None, max_depth: int = 3) -> Sections:
    """Flatten a JSON/YAML structure into sections.

    Keys become heading_path entries. Leaf values become section content.
    Arrays of objects produce one section per element.
    """
    if path is None:
        path = []

    sections: Sections = []

    if isinstance(data, dict):
        for key, value in data.items():
            current_path = [*path, str(key)]
            if len(current_path) >= max_depth or not isinstance(value, (dict, list)):
                sections.append((current_path, _value_to_text(value)))
            else:
                sections.extend(_flatten_json(value, current_path, max_depth))
    elif isinstance(data, list):
        if all(isinstance(item, dict) for item in data) and data:
            for i, item in enumerate(data):
                item_label = _item_label(item, i)
                current_path = [*path, item_label]
                if len(current_path) >= max_depth:
                    sections.append((current_path, _value_to_text(item)))
                else:
                    sections.extend(_flatten_json(item, current_path, max_depth))
        else:
            sections.append((path, _value_to_text(data)))
    else:
        sections.append((path, _value_to_text(data)))

    return sections


def _item_label(item: dict, index: int) -> str:
    """Generate a label for an array item, using a name/id/title field if available."""
    for key in ("name", "id", "title", "key"):
        if key in item:
            return str(item[key])
    return f"[{index}]"


def _value_to_text(value: object) -> str:
    """Convert a value to readable text."""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False)


@register_parser("json")
def parse_json(content: str) -> Sections:
    """Parse JSON content into sections using key paths as heading paths."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return [([], content)]

    sections = _flatten_json(data)
    return sections if sections else [([], content)]


@register_parser("yaml")
def parse_yaml(content: str) -> Sections:
    """Parse YAML content into sections. Delegates to _flatten_json after loading."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return [([], content)]

    if data is None:
        return [([], content)]

    sections = _flatten_json(data)
    return sections if sections else [([], content)]


@register_parser("rst")
def parse_rst(content: str) -> Sections:
    """Parse reStructuredText content into sections.

    Detects headings by adornment lines (===, ---, ~~~, etc.).
    Hierarchy is determined by order of first appearance of each adornment character.
    """
    sections: Sections = []
    current_path: list[str] = []
    current_levels: list[int] = []
    current_content: list[str] = []

    adornment_chars: list[str] = []  # order of first appearance determines hierarchy
    adornment_pattern = re.compile(r"^([=\-~`:.'^\"#*+_!])\1{2,}$")

    lines = content.split("\n")
    i = 0

    while i < len(lines):
        # Check for heading: line followed by adornment of same length or longer
        if (
            i + 1 < len(lines)
            and lines[i].strip()
            and not adornment_pattern.match(lines[i])
            and adornment_pattern.match(lines[i + 1].rstrip())
            and len(lines[i + 1].rstrip()) >= len(lines[i].rstrip())
        ):
            # Save previous section
            section_text = "\n".join(current_content).strip()
            if section_text:
                sections.append((list(current_path), section_text))
            current_content = []

            heading_text = lines[i].strip()
            adornment_char = lines[i + 1].rstrip()[0]

            if adornment_char not in adornment_chars:
                adornment_chars.append(adornment_char)
            level = adornment_chars.index(adornment_char) + 1

            while current_levels and current_levels[-1] >= level:
                current_levels.pop()
                if current_path:
                    current_path.pop()

            current_path.append(heading_text)
            current_levels.append(level)
            i += 2
        else:
            current_content.append(lines[i])
            i += 1

    section_text = "\n".join(current_content).strip()
    if section_text:
        sections.append((list(current_path), section_text))

    return sections


@register_parser("plaintext")
def parse_plaintext(content: str) -> Sections:
    """Parse plain text by splitting on blank lines (paragraphs)."""
    paragraphs = re.split(r"\n\s*\n", content)
    sections: Sections = []
    for para in paragraphs:
        text = para.strip()
        if text:
            sections.append(([], text))
    return sections if sections else [([], content)]
