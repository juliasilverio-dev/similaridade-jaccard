"""Cálculo de Jaccard com conjuntos de palavras, independente do Flask."""

import re
import unicodedata
from dataclasses import dataclass

from app.config import MAX_DISPLAYED_WORDS

# Letras e números Unicode; pontuação, símbolos e sublinhados separam palavras.
WORD_PATTERN = re.compile(r"[^\W_]+")


class EmptyTextError(ValueError):
    """O texto não contém letras ou números para comparar."""


@dataclass(frozen=True)
class TextStats:
    total_words: int
    words: frozenset[str]

    def __post_init__(self) -> None:
        if not self.words or self.total_words < len(self.words):
            raise EmptyTextError("O documento deve conter pelo menos uma palavra ou número.")


def tokenize(text: str) -> list[str]:
    """Uniformiza maiúsculas/minúsculas e extrai palavras, preservando acentos."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = unicodedata.normalize("NFC", normalized.casefold())
    return WORD_PATTERN.findall(normalized)


def analyze_text(text: str) -> TextStats:
    tokens = tokenize(text)
    return TextStats(total_words=len(tokens), words=frozenset(tokens))


def word_group(words: frozenset[str], limit: int) -> dict:
    """Limita a lista exibida; a contagem continua considerando todas as palavras."""
    displayed = sorted(words)[:limit]
    return {
        "quantidade": len(words),
        "palavras": displayed,
        "omitidas": len(words) - len(displayed),
    }


def compare_stats(
    text_a: TextStats,
    text_b: TextStats,
    *,
    display_limit: int = MAX_DISPLAYED_WORDS,
) -> dict:
    if display_limit < 1:
        raise ValueError("O limite de palavras exibidas deve ser positivo.")

    # O cálculo principal: interseção dividida pela união dos dois conjuntos.
    words_a, words_b = text_a.words, text_b.words
    intersection = words_a & words_b
    union = words_a | words_b
    similarity = len(intersection) / len(union)

    # Os nomes em português correspondem aos campos usados nos templates HTML.
    return {
        "similaridade": similarity,
        "percentual_formatado": f"{similarity * 100:.2f}%".replace(".", ","),
        "documento_a": {
            "total_palavras": text_a.total_words,
            "palavras_unicas": len(words_a),
        },
        "documento_b": {
            "total_palavras": text_b.total_words,
            "palavras_unicas": len(words_b),
        },
        "intersecao": word_group(intersection, display_limit),
        "uniao": {"quantidade": len(union)},
        "exclusivas_a": word_group(words_a - words_b, display_limit),
        "exclusivas_b": word_group(words_b - words_a, display_limit),
    }


def compare_texts(
    text_a: str,
    text_b: str,
    *,
    display_limit: int = MAX_DISPLAYED_WORDS,
) -> dict:
    """Permite usar o comparador diretamente, sem iniciar o servidor."""
    return compare_stats(analyze_text(text_a), analyze_text(text_b), display_limit=display_limit)
