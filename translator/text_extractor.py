"""Extraction utilities for manipulating Story XML within IDML files."""

from __future__ import annotations

from lxml import etree
import html
import re

TAG_PATTERN = re.compile(r"<[^>]+>")


def _tags_to_placeholders(text: str) -> tuple[str, list[str]]:
    """Replace XML tags in ``text`` with numbered placeholders."""

    tags: list[str] = []

    def repl(match: re.Match[str]) -> str:
        tags.append(match.group(0))
        return f"[[TAG{len(tags)}]]"

    return TAG_PATTERN.sub(repl, text), tags


def _placeholders_to_tags(text: str, tags: list[str]) -> str:
    """Reinsert ``tags`` into ``text`` replacing placeholders."""
    text = html.escape(text, quote=False)
    for i, tag in enumerate(tags, 1):
        text = text.replace(f"[[TAG{i}]]", tag)
    return text


def _set_inner_xml(el: etree._Element, xml: str) -> None:
    """Replace contents of ``el`` with parsed ``xml``."""

    for child in list(el):
        el.remove(child)
    el.text = None
    wrapper = etree.fromstring(f"<wrapper>{xml}</wrapper>")
    el.text = wrapper.text
    for child in wrapper:
        el.append(child)


def load_story_xml(story_path: str) -> etree._ElementTree:
    """Load a Story XML file and return an ``ElementTree`` instance."""

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(story_path), parser)
    return tree


def extract_content_elements(
    tree: etree._ElementTree,
) -> list[tuple[etree._Element, str, list[str]]]:
    """Return all ``<Content>`` elements containing translatable text."""
    # IDML soubory používají výchozí XML jmenné prostory, takže běžný XPath
    # '//Content' by nenašel žádné elementy. Hledáme proto podle jména
    # elementu bez ohledu na namespace.
    content_elements = tree.xpath('//*[local-name()="Content"]')
    result = []
    for el in content_elements:
        inner = (el.text or '') + ''.join(
            etree.tostring(child, encoding='unicode') for child in el
        )
        if inner.strip():
            text, tags = _tags_to_placeholders(inner)
            result.append((el, text, tags))
    return result


def update_content_elements(
    content_list: list[tuple[etree._Element, str, list[str]]],
    translations: list[str],
) -> None:
    """Replace the ``<Content>`` elements with their translated counterparts."""
    for (el, _, tags), new_text in zip(content_list, translations):
        xml = _placeholders_to_tags(new_text, tags)
        _set_inner_xml(el, xml)


def save_story_xml(tree: etree._ElementTree, output_path: str) -> None:
    """Write ``tree`` back to ``output_path`` preserving formatting."""
    tree.write(str(output_path), encoding='UTF-8', pretty_print=True, xml_declaration=True)
