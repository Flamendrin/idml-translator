"""Extraction utilities for manipulating Story XML within IDML files."""

from __future__ import annotations

from lxml import etree

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
        if el.text and el.text.strip():  # ignoruj prázdné
            result.append((el, el.text))
    return result

def update_content_elements(content_list, translations):
    """
    Přepíše obsah elementů přeloženým textem
    """
    for (el, _), new_text in zip(content_list, translations):
        el.text = new_text

def save_story_xml(tree, output_path):
    """
    Uloží zpět upravený XML strom
    """
    tree.write(str(output_path), encoding='UTF-8', pretty_print=True, xml_declaration=True)
