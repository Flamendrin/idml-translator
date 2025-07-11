from lxml import etree
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator.text_extractor import extract_content_elements, update_content_elements  # noqa: E402


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
    texts = [text for _, text, _ in results]
    assert texts == ["First", "Second"]


def test_extract_and_update_with_markup():
    xml = """
    <Root>
        <Content>Hello<b>bold</b>!</Content>
    </Root>
    """
    tree = etree.fromstring(xml)
    results = extract_content_elements(tree)
    assert results[0][1] == "Hello[[TAG1]]bold[[TAG2]]!"
    assert results[0][2] == ["<b>", "</b>"]

    update_content_elements(results, ["Ahoj[[TAG1]]tučně[[TAG2]]!"])
    content = etree.tostring(tree, encoding="unicode")
    assert "Ahoj<b>tučně</b>!" in content


def test_extract_and_update_with_br():
    xml = """
    <Root>
        <Content>Hello<br/>World</Content>
    </Root>
    """
    tree = etree.fromstring(xml)
    results = extract_content_elements(tree)
    assert results[0][1] == "Hello[[TAG1]]World"
    assert results[0][2] == ["<br/>"]

    update_content_elements(results, ["Ahoj[[TAG1]]Svete"])
    content = etree.tostring(tree, encoding="unicode")
    assert "Ahoj<br/>Svete" in content


def test_update_content_elements_escapes_ampersand():
    xml = """
    <Root>
        <Content>Hello<b>bold</b></Content>
    </Root>
    """
    tree = etree.fromstring(xml)
    results = extract_content_elements(tree)
    update_content_elements(results, ["Hi & [[TAG1]]x[[TAG2]]"])
    content = etree.tostring(tree, encoding="unicode")
    etree.fromstring(content)
    assert "Hi &amp; <b>x</b>" in content
