"""Infraestrutura de testes dos templates, sem duplicar o serviço de domínio."""

from dataclasses import dataclass, field
from html.parser import HTMLParser

import pytest
from flask import render_template
from jinja2 import StrictUndefined

from app import create_app
from app.routes import page_context


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def text(self):
        return "".join(
            child.text if isinstance(child, Element) else child for child in self.children
        )

    def find(self, tag=None, **attrs):
        matches = []
        if (tag is None or tag == self.tag) and all(
            self.attrs.get(key) == value for key, value in attrs.items()
        ):
            matches.append(self)
        for child in self.children:
            if isinstance(child, Element):
                matches.extend(child.find(tag, **attrs))
        return matches


class DocumentParser(HTMLParser):
    void_tags = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in self.void_tags:
            self.stack.append(element)

    def handle_endtag(self, tag):
        assert self.stack[-1].tag == tag, f"Fechamento HTML inconsistente: {tag}"
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)


@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    app.jinja_env.undefined = StrictUndefined
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def parse_html():
    return lambda html: DocumentParser(html).root


@pytest.fixture
def render(app, parse_html):
    def render_page(template="index.html", **overrides):
        with app.test_request_context("/"):
            html = render_template(template, **page_context(**overrides))
        return html, parse_html(html)

    return render_page


@pytest.fixture
def sample_result():
    return {
        "similaridade": 0.75,
        "percentual_formatado": "75,00%",
        "documento_a": {"total_palavras": 7, "palavras_unicas": 7},
        "documento_b": {"total_palavras": 7, "palavras_unicas": 7},
        "intersecao": {
            "quantidade": 6,
            "palavras": ["aluno", "e", "estuda", "o", "python", "sistemas"],
            "omitidas": 0,
        },
        "uniao": {"quantidade": 8},
        "exclusivas_a": {"quantidade": 1, "palavras": ["desenvolve"], "omitidas": 0},
        "exclusivas_b": {"quantidade": 1, "palavras": ["cria"], "omitidas": 0},
    }
