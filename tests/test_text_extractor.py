import pytest
from lxml import etree
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator.text_extractor import extract_content_elements


def test_extract_content_elements_ignores_empty():
    xml = """
    <Root>
        <Content>First</Content>
        <Content>   </Content>
        <Content>Second</Content>
        <Content></Content>
    </Root>
    """
    tree = etree.fromstring(xml)
    results = extract_content_elements(tree)
    texts = [text for _, text in results]
    assert texts == ["First", "Second"]
