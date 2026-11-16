"""Estrutura acessível e contraste da paleta real usada no CSS."""

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest


@pytest.mark.parametrize("state", ["initial", "result", "validation", "global", "error_page"])
def test_semantics_ids_and_aria_references_are_consistent(render, sample_result, state):
    options = {}
    if state == "result":
        options["resultado"] = sample_result
    elif state == "validation":
        options["erros_campos"] = {"documento_a": ["Corrija A."], "documento_b": ["Corrija B."]}
    elif state == "global":
        options["erro_global"] = "Não foi possível processar."
    elif state == "error_page":
        options.update(template="error.html", status_code=413, erro_global="Limite excedido.")
    _, document = render(**options)
    assert document.find("html")[0].attrs["lang"] == "pt-BR"
    assert len(document.find("h1")) == 1
    assert len(document.find("main")) == 1
    assert document.find("meta", charset="utf-8")
    assert document.find("meta", name="viewport")
    assert document.find("a", href="#conteudo")
    elements = document.find()
    ids = [element.attrs["id"] for element in elements if "id" in element.attrs]
    assert len(ids) == len(set(ids)), "IDs devem ser únicos em cada página."
    for element in elements:
        for attribute in ("aria-describedby", "aria-labelledby"):
            for reference in element.attrs.get(attribute, "").split():
                assert reference in ids
        if element.tag == "label":
            assert element.attrs["for"] in ids
        assert "onclick" not in element.attrs
        assert "style" not in element.attrs
        for attribute in ("href", "src", "action"):
            if attribute in element.attrs:
                assert not urlsplit(element.attrs[attribute]).netloc
    if state == "result":
        meter = document.find("meter")[0]
        assert meter.attrs["min"] == "0"
        assert meter.attrs["max"] == "1"
        assert meter.attrs["aria-label"] == "Similaridade de Jaccard"


def relative_luminance(color):
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return sum(
        weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True)
    )


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("ink", "page"),
        ("ink", "surface"),
        ("muted", "page"),
        ("muted", "surface"),
        ("accent", "page"),
        ("accent", "accent-soft"),
        ("surface", "accent"),
        ("surface", "accent-hover"),
        ("error", "error-soft"),
        ("error", "surface"),
    ],
)
def test_text_palette_meets_minimum_contrast(foreground, background):
    css = (Path(__file__).resolve().parents[1] / "static/css/styles.css").read_text()
    palette = dict(re.findall(r"--([\w-]+):\s*(#[\da-fA-F]{6})", css))
    lighter, darker = sorted(
        (relative_luminance(palette[foreground]), relative_luminance(palette[background])),
        reverse=True,
    )
    contrast = (lighter + 0.05) / (darker + 0.05)
    assert contrast >= 4.5, f"Contraste insuficiente: {foreground}/{background}: {contrast:.2f}"
