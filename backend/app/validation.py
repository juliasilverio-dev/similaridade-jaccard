"""Validação de formulário antes da comparação."""

from dataclasses import dataclass

from werkzeug.datastructures import MultiDict

from app.jaccard import EmptyTextError, TextStats, analyze_text

TRUNCATION_NOTICE = "O conteúdo exibido foi limitado aos primeiros {limit} caracteres."


@dataclass
class FormData:
    documents: dict[str, str]
    errors: dict[str, list[str]]
    analyses: dict[str, TextStats]

    @property
    def is_valid(self) -> bool:
        return not any(self.errors.values())


def validate_documents(form: MultiDict[str, str], *, character_limit: int) -> FormData:
    documents: dict[str, str] = {}
    errors: dict[str, list[str]] = {}
    analyses: dict[str, TextStats] = {}
    formatted_limit = f"{character_limit:,}".replace(",", ".")

    for field, label in (("documento_a", "A"), ("documento_b", "B")):
        values = form.getlist(field)
        text = values[0] if values else ""
        documents[field] = text[:character_limit]
        errors[field] = []
        message = None

        if len(values) > 1:
            message = f"Envie apenas um conteúdo para o documento {label}."
        elif len(text) > character_limit:
            message = f"O documento {label} deve ter no máximo {formatted_limit} caracteres."
        elif not text.strip():
            message = f"Informe o documento {label}."
        else:
            try:
                analyses[field] = analyze_text(text)
            except EmptyTextError:
                message = f"O documento {label} deve conter pelo menos uma palavra ou número."

        if message is not None:
            if len(text) > character_limit:
                notice = TRUNCATION_NOTICE.format(limit=formatted_limit)
                message = f"{message} {notice}"
            errors[field].append(message)

    return FormData(documents=documents, errors=errors, analyses=analyses)
