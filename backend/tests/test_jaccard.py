"""Regras matemáticas e de normalização especificadas em T01–T13."""

import unicodedata

import pytest

from app.jaccard import (
    EmptyTextError,
    TextStats,
    analyze_text,
    compare_texts,
    tokenize,
)
from app.routes import EXAMPLE_DOCUMENT_A, EXAMPLE_DOCUMENT_B


def test_official_example_matches_complete_contract():
    assert compare_texts(EXAMPLE_DOCUMENT_A, EXAMPLE_DOCUMENT_B) == {
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


@pytest.mark.parametrize(
    ("text_a", "text_b", "totals", "unique_counts", "intersection", "union", "percentage"),
    [
        ("Casa, casa! AZUL.", "casa azul", (3, 2), (2, 2), 2, 2, "100,00%"),
        ("gato cachorro", "livro mesa", (2, 2), (2, 2), 0, 4, "0,00%"),
        ("a a b", "b c", (3, 2), (2, 2), 1, 3, "33,33%"),
        ("um dois três", "três um dois", (3, 3), (3, 3), 3, 3, "100,00%"),
        ("bem-estar casa,azul", "bem estar casa azul", (4, 4), (4, 4), 4, 4, "100,00%"),
        ("casa\nazul\tverde", "casa azul verde", (3, 3), (3, 3), 3, 3, "100,00%"),
        ("avó", "avo", (1, 1), (1, 1), 0, 2, "0,00%"),
        ("versao2_2026", "versao2 2026", (2, 2), (2, 2), 2, 2, "100,00%"),
        ("AÇÃO", "ação", (1, 1), (1, 1), 1, 1, "100,00%"),
        ("Straße", "STRASSE", (1, 1), (1, 1), 1, 1, "100,00%"),
    ],
)
def test_comparison_rules(text_a, text_b, totals, unique_counts, intersection, union, percentage):
    result = compare_texts(text_a, text_b)
    assert result["documento_a"] == {
        "total_palavras": totals[0],
        "palavras_unicas": unique_counts[0],
    }
    assert result["documento_b"] == {
        "total_palavras": totals[1],
        "palavras_unicas": unique_counts[1],
    }
    assert result["intersecao"]["quantidade"] == intersection
    assert result["uniao"]["quantidade"] == union
    assert result["similaridade"] == pytest.approx(intersection / union)
    assert result["percentual_formatado"] == percentage


def test_unicode_composed_and_decomposed_are_equivalent():
    decomposed = unicodedata.normalize("NFD", "ação")
    assert decomposed != "ação"
    assert compare_texts("ação", decomposed)["similaridade"] == 1.0


def test_punctuation_apostrophes_symbols_and_numbers():
    assert tokenize("d'água texto_base 2026 versao2 🙂 + casa,azul") == [
        "d",
        "água",
        "texto",
        "base",
        "2026",
        "versao2",
        "casa",
        "azul",
    ]


def test_stopwords_accents_and_original_text_are_preserved():
    original = "  O aluno e a avó.\n"
    assert tokenize(original) == ["o", "aluno", "e", "a", "avó"]
    assert original == "  O aluno e a avó.\n"
    assert analyze_text("Casa casa").words == frozenset({"casa"})


@pytest.mark.parametrize("invalid", ["", "   ", "\n\t", "!!!", "🙂", "___ + —"])
@pytest.mark.parametrize("side", ["a", "b"])
def test_empty_documents_raise_domain_error(invalid, side):
    with pytest.raises(EmptyTextError, match="palavra ou número"):
        compare_texts(invalid if side == "a" else "válido", invalid if side == "b" else "válido")


def test_both_empty_and_manually_invalid_analyses_are_rejected():
    with pytest.raises(EmptyTextError):
        compare_texts("!!!", "🙂")
    with pytest.raises(EmptyTextError):
        TextStats(total_words=0, words=frozenset({"palavra"}))


@pytest.mark.parametrize(
    ("text_a", "text_b"),
    [
        (EXAMPLE_DOCUMENT_A, EXAMPLE_DOCUMENT_B),
        ("a a b", "b c d"),
        ("x", "y"),
        ("um dois", "dois um um"),
    ],
)
def test_symmetry_range_and_counts(text_a, text_b):
    forward = compare_texts(text_a, text_b)
    backward = compare_texts(text_b, text_a)
    assert 0 <= forward["similaridade"] <= 1
    assert forward["similaridade"] == backward["similaridade"]
    assert forward["intersecao"] == backward["intersecao"]
    assert forward["uniao"] == backward["uniao"]
    assert forward["documento_a"] == backward["documento_b"]
    assert forward["exclusivas_a"] == backward["exclusivas_b"]


def test_each_list_is_limited_without_changing_calculation():
    shared = {f"comum{i:03}" for i in range(70)}
    only_a = {f"alfa{i:03}" for i in range(65)}
    only_b = {f"beta{i:03}" for i in range(80)}
    result = compare_texts(" ".join(shared | only_a), " ".join(shared | only_b))
    for key, words in (("intersecao", shared), ("exclusivas_a", only_a), ("exclusivas_b", only_b)):
        assert result[key] == {
            "quantidade": len(words),
            "palavras": sorted(words)[:50],
            "omitidas": len(words) - 50,
        }
    assert result["uniao"]["quantidade"] == 215
    assert result["similaridade"] == pytest.approx(70 / 215)


def test_display_limit_does_not_round_score():
    result = compare_texts("a b", "b c", display_limit=1)
    assert result["similaridade"] == 1 / 3
    assert result["percentual_formatado"] == "33,33%"
    assert result["intersecao"]["palavras"] == ["b"]


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_display_limits_are_rejected(limit):
    with pytest.raises(ValueError, match="positivo"):
        compare_texts("a", "b", display_limit=limit)
