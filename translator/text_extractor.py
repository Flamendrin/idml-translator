"""Extraction utilities for manipulating Story XML within IDML files."""

from __future__ import annotations

from lxml import etree
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

def load_story_xml(story_path):
    """
    Načte XML strom ze souboru
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(story_path), parser)
    return tree

def extract_content_elements(tree):
    """
    Najde všechny <Content> elementy s textem k překladu.
    Elementy bez textu ignoruje.
    Vrací seznam (element, původní text)
    """
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

def update_content_elements(content_list, translations):
    """
    Přepíše obsah elementů přeloženým textem
    """
    for (el, _, tags), new_text in zip(content_list, translations):
        xml = _placeholders_to_tags(new_text, tags)
        _set_inner_xml(el, xml)

def save_story_xml(tree, output_path):
    """
    Uloží zpět upravený XML strom
    """
    tree.write(str(output_path), encoding='UTF-8', pretty_print=True, xml_declaration=True)
