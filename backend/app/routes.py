"""As duas rotas, os dados da página e o exemplo da apresentação."""

from typing import Any

from flask import Blueprint, current_app, render_template, request
from werkzeug.exceptions import UnsupportedMediaType

from app.jaccard import compare_stats
from app.validation import validate_documents

web = Blueprint("web", __name__)

EXAMPLE_DOCUMENT_A = "O aluno estuda Python e desenvolve sistemas."
EXAMPLE_DOCUMENT_B = "O aluno estuda Python e cria sistemas."


def get_example() -> dict[str, str]:
    return {
        "titulo": "Exemplo de comparação para análise de possível plágio",
        "documento_a": EXAMPLE_DOCUMENT_A,
        "documento_b": EXAMPLE_DOCUMENT_B,
        "percentual_esperado": "75,00%",
    }


def page_context(**overrides: Any) -> dict[str, Any]:
    """Cria os dados de uma página, sem guardar textos entre requisições."""
    context = {
        "documentos": {"documento_a": "", "documento_b": ""},
        "erros_campos": {"documento_a": [], "documento_b": []},
        "erro_global": None,
        "resultado": None,
        "limites": {
            "max_caracteres_por_documento": current_app.config["MAX_DOCUMENT_CHARACTERS"],
            "max_tokens_exibidos": current_app.config["MAX_DISPLAYED_WORDS"],
        },
        "exemplo": get_example(),
    }
    context.update(overrides)
    return context


@web.get("/")
def index():
    context = page_context()
    if request.args.get("exemplo") == "plagio":
        example = get_example()
        context["documentos"] = {
            "documento_a": example["documento_a"],
            "documento_b": example["documento_b"],
        }
    return render_template("index.html", **context)


@web.post("/comparar")
def compare():
    # Não aceitar uploads: o contrato utiliza exclusivamente formulário textual.
    if request.mimetype not in ("", "application/x-www-form-urlencoded"):
        raise UnsupportedMediaType()

    validated = validate_documents(
        request.form, character_limit=current_app.config["MAX_DOCUMENT_CHARACTERS"]
    )
    context = page_context(documentos=validated.documents, erros_campos=validated.errors)
    if not validated.is_valid:
        return render_template("index.html", **context), 422

    context["resultado"] = compare_stats(
        validated.analyses["documento_a"],
        validated.analyses["documento_b"],
        display_limit=current_app.config["MAX_DISPLAYED_WORDS"],
    )
    return render_template("index.html", **context), 200
