"""Contrato HTTP, templates, validação e privacidade: T14–T23."""

import io
import logging
from html.parser import HTMLParser
from urllib.parse import urlencode

import pytest
from flask import abort
from werkzeug.datastructures import MultiDict

from app import REQUEST_TOO_LARGE_MESSAGE, create_app, routes, validation
from app.config import MAX_DOCUMENT_CHARACTERS, MAX_REQUEST_BYTES
from app.routes import EXAMPLE_DOCUMENT_A, EXAMPLE_DOCUMENT_B, get_example


def post_documents(client, document_a=EXAMPLE_DOCUMENT_A, document_b=EXAMPLE_DOCUMENT_B):
    return client.post(
        "/comparar",
        data={"documento_a": document_a, "documento_b": document_b},
        content_type="application/x-www-form-urlencoded",
    )


class TextareaParser(HTMLParser):
    """Recupera texto como no textarea HTML, incluindo a regra do primeiro LF."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag == "textarea":
            self.active = dict(attrs)["name"]
            self.values[self.active] = ""

    def handle_data(self, data):
        if self.active is not None:
            self.values[self.active] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.values[self.active] = self.values[self.active].removeprefix("\n")
            self.active = None


def textarea_values(response):
    parser = TextareaParser()
    parser.feed(response.text)
    return parser.values


def test_factory_default_configuration():
    app = create_app()
    assert app.debug is False
    assert app.testing is False
    assert app.config["MAX_CONTENT_LENGTH"] == 2 * 1024 * 1024
    assert app.config["MAX_FORM_MEMORY_SIZE"] == 2 * 1024 * 1024
    assert app.secret_key is None


def test_initial_page_context_and_educational_content(client, rendered):
    response = client.get("/")
    assert response.status_code == 200
    assert rendered[-1][0] == "index.html"
    context = rendered[-1][1]
    assert context["documentos"] == {"documento_a": "", "documento_b": ""}
    assert context["erros_campos"] == {"documento_a": [], "documento_b": []}
    assert context["erro_global"] is None
    assert context["resultado"] is None
    assert context["limites"] == {"max_caracteres_por_documento": 100000, "max_tokens_exibidos": 50}
    assert context["exemplo"] == get_example()
    assert 'id="resultado"' not in response.text
    assert 'method="post" action="/comparar"' in response.text
    assert 'lang="pt-BR"' in response.text
    for content in (
        "Limitações para análise de plágio",
        "Sinônimos, paráfrases e traduções",
        "ordem das palavras",
        "artigos e preposições",
        "documento muito maior",
        "não pesquisa fontes na internet",
        "não comprova plágio",
        "limiar de plágio",
    ):
        assert content in response.text


def test_example_is_prefilled_but_not_calculated(client, rendered):
    response = client.get("/?exemplo=plagio")
    assert response.status_code == 200
    assert textarea_values(response) == {
        "documento_a": EXAMPLE_DOCUMENT_A,
        "documento_b": EXAMPLE_DOCUMENT_B,
    }
    assert rendered[-1][1]["resultado"] is None
    assert 'id="resultado"' not in response.text
    assert "/?exemplo=plagio#comparacao" in response.text


@pytest.mark.parametrize("value", ["desconhecido", "../../etc/passwd", "<script>bad</script>"])
def test_unknown_examples_are_ignored(client, value):
    response = client.get("/", query_string={"exemplo": value})
    assert response.status_code == 200
    assert textarea_values(response) == {"documento_a": "", "documento_b": ""}
    assert value not in response.text


def test_valid_post_renders_result_without_redirect_or_session(client, rendered):
    response = post_documents(client)
    assert response.status_code == 200
    assert 'id="resultado"' in response.text
    assert "6 / 8 = 75,00%" in response.text
    assert response.headers.get("Location") is None
    assert response.headers.get("Set-Cookie") is None
    assert textarea_values(response) == {
        "documento_a": EXAMPLE_DOCUMENT_A,
        "documento_b": EXAMPLE_DOCUMENT_B,
    }
    context = rendered[-1][1]
    assert context["resultado"]["similaridade"] == 0.75
    assert context["erros_campos"] == {"documento_a": [], "documento_b": []}


@pytest.mark.parametrize(
    ("text_a", "text_b", "expected"),
    [("casa casa", "CASA!", "100,00%"), ("casa", "livro", "0,00%")],
)
def test_extreme_results_are_visible(client, text_a, text_b, expected):
    response = post_documents(client, text_a, text_b)
    assert response.status_code == 200
    assert 'id="resultado"' in response.text
    assert f'<p class="score">{expected}</p>' in response.text
    assert "Nenhuma palavra neste grupo." in response.text


@pytest.mark.parametrize("field", ["documento_a", "documento_b"])
@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "Informe o documento {label}."),
        ("", "Informe o documento {label}."),
        (" \n\t", "Informe o documento {label}."),
        ("!!!", "O documento {label} deve conter pelo menos uma palavra ou número."),
        ("🙂", "O documento {label} deve conter pelo menos uma palavra ou número."),
    ],
)
def test_invalid_fields_preserve_other_document(client, rendered, field, value, message):
    data = {"documento_a": "Texto A intacto.", "documento_b": "Texto B intacto."}
    if value is None:
        del data[field]
    else:
        data[field] = value
    response = client.post("/comparar", data=data, content_type="application/x-www-form-urlencoded")
    label = "A" if field == "documento_a" else "B"
    assert response.status_code == 422
    assert message.format(label=label) in response.text
    context = rendered[-1][1]
    assert context["erros_campos"][field] == [message.format(label=label)]
    other = "documento_b" if field == "documento_a" else "documento_a"
    assert context["documentos"][other] == data[other]
    assert context["resultado"] is None
    assert 'aria-invalid="true"' in response.text
    assert f'href="#{field}"' in response.text
    assert 'id="resultado"' not in response.text


def test_empty_post_has_both_validation_errors(client, rendered):
    response = client.post("/comparar")
    assert response.status_code == 422
    assert rendered[-1][1]["erros_campos"] == {
        "documento_a": ["Informe o documento A."],
        "documento_b": ["Informe o documento B."],
    }


def test_validation_reports_both_errors_in_one_response(client, rendered):
    response = post_documents(client, "", "!!!")
    assert response.status_code == 422
    assert rendered[-1][1]["erros_campos"] == {
        "documento_a": ["Informe o documento A."],
        "documento_b": ["O documento B deve conter pelo menos uma palavra ou número."],
    }


@pytest.mark.parametrize("field", ["documento_a", "documento_b"])
def test_exact_individual_character_limit_is_accepted(client, field):
    data = {"documento_a": "palavra", "documento_b": "palavra"}
    data[field] = "a" * MAX_DOCUMENT_CHARACTERS
    response = client.post("/comparar", data=data)
    assert response.status_code == 200
    assert textarea_values(response)[field] == data[field]


@pytest.mark.parametrize("field", ["documento_a", "documento_b"])
def test_oversized_document_is_rejected_before_normalizing(client, rendered, monkeypatch, field):
    original_analyze = validation.analyze_text

    def checked_analyze(text):
        assert len(text) <= MAX_DOCUMENT_CHARACTERS
        return original_analyze(text)

    monkeypatch.setattr("app.validation.analyze_text", checked_analyze)
    data = {"documento_a": "válido", "documento_b": "válido"}
    data[field] = "a" * (MAX_DOCUMENT_CHARACTERS + 1)
    response = client.post("/comparar", data=data)
    assert response.status_code == 422
    context = rendered[-1][1]
    label = "A" if field == "documento_a" else "B"
    assert context["erros_campos"][field] == [
        f"O documento {label} deve ter no máximo 100.000 caracteres. "
        "O conteúdo exibido foi limitado aos primeiros 100.000 caracteres."
    ]
    assert len(context["documentos"][field]) == MAX_DOCUMENT_CHARACTERS
    assert len(textarea_values(response)[field]) == MAX_DOCUMENT_CHARACTERS
    assert context["resultado"] is None


def test_character_limit_uses_python_unicode_length(client):
    # 50.000 emojis + uma letra: 50.001 code points, 100.001 unidades UTF-16.
    document = "🙂" * 50_000 + "a"
    response = post_documents(client, document, "a")
    assert response.status_code == 200
    assert textarea_values(response)["documento_a"] == document
    assert "maxlength=" not in response.text


@pytest.mark.parametrize("field", ["documento_a", "documento_b"])
def test_repeated_fields_are_rejected(client, rendered, field):
    data = MultiDict(
        [("documento_a", "primeiro A"), ("documento_b", "primeiro B"), (field, "segundo")]
    )
    response = client.post("/comparar", data=data)
    label = "A" if field == "documento_a" else "B"
    assert response.status_code == 422
    assert rendered[-1][1]["erros_campos"][field] == [
        f"Envie apenas um conteúdo para o documento {label}."
    ]
    assert rendered[-1][1]["documentos"][field] == f"primeiro {label}"
    assert rendered[-1][1]["resultado"] is None


def test_repetition_takes_priority_over_size_and_limits_redisplay(client, rendered):
    data = MultiDict(
        [
            ("documento_a", "a" * (MAX_DOCUMENT_CHARACTERS + 1)),
            ("documento_a", "outro"),
            ("documento_b", "válido"),
        ]
    )
    response = client.post("/comparar", data=data)
    assert response.status_code == 422
    assert rendered[-1][1]["erros_campos"]["documento_a"] == [
        "Envie apenas um conteúdo para o documento A. "
        "O conteúdo exibido foi limitado aos primeiros 100.000 caracteres."
    ]
    assert len(rendered[-1][1]["documentos"]["documento_a"]) == MAX_DOCUMENT_CHARACTERS


def test_additional_fields_do_not_participate_in_comparison(client, rendered):
    response = client.post(
        "/comparar",
        data={"documento_a": "a", "documento_b": "a", "similaridade": "0", "extra": "privado"},
    )
    assert response.status_code == 200
    assert rendered[-1][1]["resultado"]["similaridade"] == 1
    assert "privado" not in response.text


def test_oversized_body_is_not_parsed_or_echoed(client, rendered, monkeypatch):
    def must_not_validate(*args, **kwargs):
        pytest.fail("Um corpo excessivo não pode chegar à validação do formulário.")

    monkeypatch.setattr(routes, "validate_documents", must_not_validate)
    sentinel = "DOCUMENTO_CONFIDENCIAL"
    body = f"documento_a={sentinel}&documento_b=" + "x" * MAX_REQUEST_BYTES
    response = client.post("/comparar", data=body, content_type="application/x-www-form-urlencoded")
    assert response.status_code == 413
    assert REQUEST_TOO_LARGE_MESSAGE in response.text
    assert sentinel not in response.text
    assert rendered[-1][1]["documentos"] == {"documento_a": "", "documento_b": ""}
    assert rendered[-1][1]["resultado"] is None
    assert rendered[-1][1]["erro_global"] == REQUEST_TOO_LARGE_MESSAGE


def test_streamed_body_without_content_length_is_also_limited(client):
    body = b"documento_a=a&documento_b=" + b"x" * MAX_REQUEST_BYTES
    response = client.open(
        "/comparar",
        method="POST",
        environ_overrides={
            "wsgi.input": io.BytesIO(body),
            "wsgi.input_terminated": True,
            "CONTENT_LENGTH": "",
            "HTTP_TRANSFER_ENCODING": "chunked",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
        },
    )
    assert response.status_code == 413


@pytest.mark.parametrize("streamed", [False, True])
def test_body_exactly_at_global_limit_is_not_rejected(client, streamed):
    prefix = b"documento_a=a&documento_b=a&ignorar="
    body = prefix + b"x" * (MAX_REQUEST_BYTES - len(prefix))
    if streamed:
        response = client.open(
            "/comparar",
            method="POST",
            environ_overrides={
                "wsgi.input": io.BytesIO(body),
                "wsgi.input_terminated": True,
                "CONTENT_LENGTH": "",
                "HTTP_TRANSFER_ENCODING": "chunked",
                "CONTENT_TYPE": "application/x-www-form-urlencoded",
            },
        )
    else:
        response = client.post(
            "/comparar", data=body, content_type="application/x-www-form-urlencoded"
        )
    assert response.status_code == 200


def test_small_streamed_body_without_content_length_is_accepted(client):
    body = urlencode({"documento_a": EXAMPLE_DOCUMENT_A, "documento_b": EXAMPLE_DOCUMENT_B})
    response = client.open(
        "/comparar",
        method="POST",
        environ_overrides={
            "wsgi.input": io.BytesIO(body.encode()),
            "wsgi.input_terminated": True,
            "CONTENT_LENGTH": "",
            "HTTP_TRANSFER_ENCODING": "chunked",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
        },
    )
    assert response.status_code == 200
    assert "6 / 8 = 75,00%" in response.text


def test_encoded_form_below_total_limit_is_accepted(client):
    # Duas entradas de 100.000 caracteres com codificação de 900.000 bytes cada.
    document = "漢" * MAX_DOCUMENT_CHARACTERS
    body = urlencode({"documento_a": document, "documento_b": document}).encode("ascii")
    assert 500_000 < len(body) < MAX_REQUEST_BYTES
    response = client.post("/comparar", data=body, content_type="application/x-www-form-urlencoded")
    assert response.status_code == 200
    assert "100,00%" in response.text


def test_invalid_followup_and_clear_do_not_reuse_previous_result(client, rendered):
    assert post_documents(client).status_code == 200
    response = post_documents(client, "!!!", "válido")
    assert response.status_code == 422
    assert 'id="resultado"' not in response.text
    assert rendered[-1][1]["resultado"] is None
    assert client.get("/").status_code == 200
    assert rendered[-1][1]["documentos"] == {"documento_a": "", "documento_b": ""}
    assert rendered[-1][1]["resultado"] is None


@pytest.mark.parametrize(
    "document",
    [
        "<script>alert(1)</script>",
        '</textarea><script>alert("teste")</script>',
        "\nPrimeira linha\nSegunda linha & <conteúdo>\n",
    ],
)
def test_original_text_is_escaped_and_preserved_in_textarea(client, caplog, document):
    with caplog.at_level(logging.DEBUG):
        response = post_documents(client, document, "válido")
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert textarea_values(response)["documento_a"] == document
    assert document not in caplog.text
    assert response.headers.get("Set-Cookie") is None
    assert response.headers.get("Location") is None
    assert document not in str(response.headers)


def test_large_word_groups_show_full_counts_and_omissions(client, rendered):
    shared = " ".join(f"comum{i}" for i in range(55))
    only_a = " ".join(f"alfa{i}" for i in range(60))
    response = post_documents(client, f"{shared} {only_a}", shared)
    assert response.status_code == 200
    assert "Exibindo 50 de 55 palavras; 5 não exibidas." in response.text
    assert "Exibindo 50 de 60 palavras; 10 não exibidas." in response.text
    assert "55 / 115 = 47,83%" in response.text
    assert rendered[-1][1]["resultado"]["uniao"]["quantidade"] == 115


@pytest.mark.parametrize(("path", "status"), [("/nao-existe", 404), ("/comparar", 405)])
def test_missing_routes_and_wrong_methods(client, path, status):
    response = client.get(path)
    assert response.status_code == status
    assert "Voltar ao formulário" in response.text
    if status == 405:
        assert "POST" in response.headers["Allow"]


@pytest.mark.parametrize("content_type", ["application/json", "multipart/form-data", "text/plain"])
def test_unsupported_media_types_do_not_create_upload_flow(client, content_type):
    response = client.post("/comparar", data="qualquer conteúdo", content_type=content_type)
    assert response.status_code == 415
    assert "formulário de texto" in response.text


@pytest.mark.parametrize("status", [400, 418])
def test_generic_http_errors_do_not_expose_descriptions(app, client, status):
    def fail():
        abort(status, description="SEGREDO_NA_EXCECAO")

    app.add_url_rule("/erro-teste", view_func=fail)
    response = client.get("/erro-teste")
    assert response.status_code == status
    assert "SEGREDO_NA_EXCECAO" not in response.text
    assert "Voltar ao formulário" in response.text


def test_internal_failure_never_logs_exception_content(app, client, monkeypatch, caplog):
    app.config["PROPAGATE_EXCEPTIONS"] = False
    secret = "CONTEUDO_PRIVADO_NAO_DEVE_VAZAR"

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(routes, "compare_stats", fail)
    with caplog.at_level(logging.ERROR):
        response = post_documents(client, secret, "válido")
    assert response.status_code == 500
    assert "Não foi possível concluir a comparação." in response.text
    assert secret not in response.text
    assert secret not in caplog.text
    assert "RuntimeError" in caplog.text
    assert "Traceback" not in response.text
    assert 'id="resultado"' not in response.text


@pytest.mark.parametrize("path", ["/", "/?exemplo=plagio", "/ausente", "/comparar"])
def test_dynamic_responses_disable_cache(client, path):
    response = client.get(path)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'none'" in response.headers["Content-Security-Policy"]


def test_cache_policy_for_post_errors_success_and_static_assets(client):
    for response in (
        post_documents(client),
        post_documents(client, "", ""),
        client.post("/comparar", data=b"x" * (MAX_REQUEST_BYTES + 1)),
        client.get("/static/nao-existe.css"),
    ):
        assert response.headers["Cache-Control"] == "no-store"
    with client.get("/static/css/styles.css") as css:
        assert css.status_code == 200
        assert css.mimetype == "text/css"
        assert css.headers["Cache-Control"] != "no-store"


def test_application_configuration_can_be_overridden_for_tests():
    app = create_app({"TESTING": True, "MAX_CONTENT_LENGTH": None})
    assert app.test_client().get("/").status_code == 200


def test_context_and_example_are_isolated_between_requests(client, rendered):
    client.get("/?exemplo=plagio")
    rendered[-1][1]["exemplo"]["documento_a"] = "não compartilhar esta alteração"
    client.get("/")
    assert rendered[-1][1]["exemplo"]["documento_a"] == EXAMPLE_DOCUMENT_A
    assert rendered[-1][1]["documentos"]["documento_a"] == ""
