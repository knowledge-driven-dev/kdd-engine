"""Tests for content parsers."""

import pytest

from kb_engine.chunking.parsers import get_parser, parse_json, parse_markdown, parse_plaintext, parse_rst, parse_yaml


@pytest.mark.unit
class TestParseMarkdown:
    """Tests for the markdown parser."""

    def test_headings_and_hierarchy(self) -> None:
        content = "# Title\n\nIntro text.\n\n## Section A\n\nContent A.\n\n### Sub A1\n\nContent A1.\n\n## Section B\n\nContent B."
        sections = parse_markdown(content)

        assert sections[0] == (["Title"], "Intro text.")
        assert sections[1] == (["Title", "Section A"], "Content A.")
        assert sections[2] == (["Title", "Section A", "Sub A1"], "Content A1.")
        assert sections[3] == (["Title", "Section B"], "Content B.")

    def test_no_headings(self) -> None:
        content = "Just plain text\nwith multiple lines."
        sections = parse_markdown(content)

        assert len(sections) == 1
        assert sections[0] == ([], "Just plain text\nwith multiple lines.")

    def test_empty_content(self) -> None:
        sections = parse_markdown("")
        assert sections == []


@pytest.mark.unit
class TestParseJson:
    """Tests for the JSON parser."""

    def test_object_key_paths(self) -> None:
        content = '{"name": "Alice", "age": 30}'
        sections = parse_json(content)

        paths = [s[0] for s in sections]
        assert ["name"] in paths
        assert ["age"] in paths

    def test_nested_object(self) -> None:
        content = '{"user": {"name": "Alice", "email": "a@b.com"}}'
        sections = parse_json(content)

        paths = [s[0] for s in sections]
        assert ["user", "name"] in paths
        assert ["user", "email"] in paths

    def test_array_of_objects(self) -> None:
        content = '[{"name": "Alice"}, {"name": "Bob"}]'
        sections = parse_json(content)

        # Each element gets its own section, labeled by name field
        paths = [s[0] for s in sections]
        assert any("Alice" in p for p in paths)
        assert any("Bob" in p for p in paths)

    def test_invalid_json_fallback(self) -> None:
        content = "not valid json {{"
        sections = parse_json(content)

        assert len(sections) == 1
        assert sections[0] == ([], content)

    def test_empty_object(self) -> None:
        content = "{}"
        sections = parse_json(content)

        # Empty object produces no keys, fallback to raw content
        assert len(sections) == 1
        assert sections[0] == ([], content)


@pytest.mark.unit
class TestParseYaml:
    """Tests for the YAML parser."""

    def test_nested_structure(self) -> None:
        content = "database:\n  host: localhost\n  port: 5432\napp:\n  name: myapp"
        sections = parse_yaml(content)

        paths = [s[0] for s in sections]
        assert ["database", "host"] in paths
        assert ["database", "port"] in paths
        assert ["app", "name"] in paths

    def test_invalid_yaml_fallback(self) -> None:
        content = ":\n  - :\n    - :"
        sections = parse_yaml(content)
        # Should not crash; returns at least one section
        assert len(sections) >= 1

    def test_empty_yaml(self) -> None:
        content = ""
        sections = parse_yaml(content)
        assert len(sections) == 1
        assert sections[0] == ([], "")


@pytest.mark.unit
class TestParseRst:
    """Tests for the RST parser."""

    def test_headings_with_underlines(self) -> None:
        content = "Title\n=====\n\nIntro text.\n\nSection A\n---------\n\nContent A.\n\nSection B\n---------\n\nContent B."
        sections = parse_rst(content)

        assert sections[0] == (["Title"], "Intro text.")
        assert sections[1] == (["Title", "Section A"], "Content A.")
        assert sections[2] == (["Title", "Section B"], "Content B.")

    def test_hierarchy_by_adornment_char(self) -> None:
        content = "Top\n===\n\nText.\n\nSub\n---\n\nSub text.\n\nSubSub\n~~~~~~\n\nDeep text."
        sections = parse_rst(content)

        assert sections[0] == (["Top"], "Text.")
        assert sections[1] == (["Top", "Sub"], "Sub text.")
        assert sections[2] == (["Top", "Sub", "SubSub"], "Deep text.")

    def test_no_headings(self) -> None:
        content = "Just some plain text\nwithout any headings."
        sections = parse_rst(content)

        assert len(sections) == 1
        assert sections[0] == ([], "Just some plain text\nwithout any headings.")


@pytest.mark.unit
class TestParsePlaintext:
    """Tests for the plaintext parser."""

    def test_paragraphs_by_blank_lines(self) -> None:
        content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        sections = parse_plaintext(content)

        assert len(sections) == 3
        assert sections[0] == ([], "First paragraph.")
        assert sections[1] == ([], "Second paragraph.")
        assert sections[2] == ([], "Third paragraph.")

    def test_single_paragraph(self) -> None:
        content = "Just one paragraph without blanks."
        sections = parse_plaintext(content)

        assert len(sections) == 1
        assert sections[0] == ([], "Just one paragraph without blanks.")

    def test_empty_content(self) -> None:
        sections = parse_plaintext("")
        assert len(sections) == 1
        assert sections[0] == ([], "")


@pytest.mark.unit
class TestGetParser:
    """Tests for the parser registry."""

    def test_get_known_parsers(self) -> None:
        for name in ("markdown", "json", "yaml", "rst", "plaintext"):
            parser = get_parser(name)
            assert callable(parser)

    def test_unknown_parser_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown parser"):
            get_parser("nonexistent")
