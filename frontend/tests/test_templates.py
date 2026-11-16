"""Testes unitários da apresentação: contrato, estados e conteúdo seguro."""

from pathlib import Path

import pytest

FRONTEND_ROOT = Path(__file__).resolve().parents[1]


def test_flask_serves_the_frontend_directory(app, client):
    assert Path(app.template_folder) == FRONTEND_ROOT / "templates"
    assert Path(app.static_folder) == FRONTEND_ROOT / "static"
    assert not (FRONTEND_ROOT.parent / "backend/app/templates/index.html").exists()
    with client.get("/static/css/styles.css") as response:
        assert response.status_code == 200
        assert response.mimetype == "text/css"
        assert response.text == (FRONTEND_ROOT / "static/css/styles.css").read_text()
    with client.get("/static/favicon.svg") as response:
        assert response.status_code == 200


def test_form_contract_and_initial_state(render):
    _, document = render()
    form = document.find("form")[0]
    assert form.attrs["action"] == "/comparar"
    assert form.attrs["method"] == "post"
    assert form.attrs["accept-charset"] == "UTF-8"
    assert len(form.find("textarea")) == 2
    for name in ("documento_a", "documento_b"):
        textarea = form.find("textarea", name=name)[0]
        assert textarea.attrs["id"] == name
        assert "required" in textarea.attrs
        assert "maxlength" not in textarea.attrs
        assert "placeholder" not in textarea.attrs
        assert "aria-invalid" not in textarea.attrs
        assert textarea.text.removeprefix("\n") == ""
        assert form.find("label", **{"for": name})
    assert len(form.find("button", type="submit")) == 1
    assert not document.find("button", type="reset")
    assert not document.find(id="resultado")


def test_limits_are_read_from_the_context(render):
    _, document = render(limites={"max_caracteres_por_documento": 1234, "max_tokens_exibidos": 50})
    assert document.text.count("Máximo de 1.234 caracteres por documento.") == 2


def test_clear_is_a_navigation_to_the_empty_form(render):
    _, document = render()
    clear = [element for element in document.find("a") if "Limpar comparação" in element.text]
    assert len(clear) == 1
    assert clear[0].attrs["href"] == "/"


def test_learning_navigation_keeps_current_inputs_and_result(render, sample_result):
    _, document = render(resultado=sample_result)
    navigation = document.find("nav")[0]
    assert [link.attrs["href"] for link in navigation.find("a")] == ["#metodo", "#limitacoes"]


def test_example_is_present_and_loads_without_calculating(client, parse_html):
    response = client.get("/?exemplo=plagio")
    document = parse_html(response.text)
    assert not document.find(id="resultado")
    assert document.find("textarea", name="documento_a")[0].text.removeprefix("\n") == (
        "O aluno estuda Python e desenvolve sistemas."
    )
    assert document.find("textarea", name="documento_b")[0].text.removeprefix("\n") == (
        "O aluno estuda Python e cria sistemas."
    )
    example = document.find(id="exemplo")[0]
    assert "Resultado esperado da demonstração" in example.text
    assert "75,00%" in example.text
    assert "Ao carregar o exemplo, os textos atuais serão substituídos." in example.text
    assert example.find("a")[0].attrs["href"] == "/?exemplo=plagio#comparacao"


def test_example_values_are_not_duplicated_in_the_template(render):
    _, document = render(
        exemplo={
            "titulo": "Demonstração recebida",
            "documento_a": "referência enviada",
            "documento_b": "análise enviada",
            "percentual_esperado": "42,00%",
        }
    )
    example = document.find(id="exemplo")[0]
    assert "referência enviada" in example.text
    assert "análise enviada" in example.text
    assert "42,00%" in example.text
    assert "O aluno estuda Python" not in example.text


def test_result_uses_formatted_value_and_does_not_recompute_score(render, sample_result):
    sample_result["percentual_formatado"] = "12,34%"
    _, document = render(resultado=sample_result)
    result = document.find(id="resultado")[0]
    assert result.find("p", **{"class": "score"})[0].text == "12,34%"
    assert "6 / 8 = 12,34%" in result.text
    assert "75,00%" not in result.text
    assert result.find("meter")[0].attrs["value"] == "0.75"
    assert "Este resultado indica sobreposição de palavras e não comprova plágio." in result.text


@pytest.mark.parametrize(
    ("score", "formatted", "explanation"),
    [
        (0.0, "0,00%", "Os conjuntos não têm palavras em comum"),
        (1.0, "100,00%", "Os conjuntos de palavras são iguais"),
        (0.75, "75,00%", "O percentual representa a razão"),
    ],
)
def test_all_valid_scores_show_result(render, sample_result, score, formatted, explanation):
    sample_result.update(similaridade=score, percentual_formatado=formatted)
    _, document = render(resultado=sample_result)
    result = document.find(id="resultado")[0]
    assert result.find("p", **{"class": "score"})[0].text == formatted
    assert explanation in result.text
    assert document.find("title")[0].text == "Resultado da comparação — Jaccard"


def test_result_word_order_and_document_counts_are_preserved(render, sample_result):
    _, document = render(resultado=sample_result)
    result = document.find(id="resultado")[0]
    shared = result.find("section", **{"aria-labelledby": "grupo-intersecao"})[0]
    assert [word.text for word in shared.find("li")] == sample_result["intersecao"]["palavras"]
    assert "6 palavras distintas" in shared.text
    exclusive = result.find("section", **{"aria-labelledby": "grupo-exclusivas_a"})[0]
    assert "1 palavra distinta" in exclusive.text
    assert "Palavras totais (ocorrências)" in result.text
    assert "Somente as palavras distintas entram no cálculo." in result.text


def test_empty_and_truncated_groups_are_explained(render, sample_result):
    sample_result["intersecao"] = {"quantidade": 0, "palavras": [], "omitidas": 0}
    sample_result["exclusivas_a"] = {
        "quantidade": 57,
        "palavras": [f"palavra{i}" for i in range(50)],
        "omitidas": 7,
    }
    _, document = render(resultado=sample_result)
    result = document.find(id="resultado")[0]
    assert "Nenhuma palavra neste grupo." in result.text
    assert "Exibindo 50 de 57 palavras; 7 não exibidas." in result.text
    assert "O cálculo considera todas as palavras, inclusive as não listadas." in result.text
    assert (
        len(result.find("section", **{"aria-labelledby": "grupo-exclusivas_a"})[0].find("li")) == 50
    )


def test_errors_are_linked_and_input_is_preserved(render):
    original = "\nTexto A com acentos e <tags>.\n"
    _, document = render(
        documentos={"documento_a": original, "documento_b": "!!!"},
        erros_campos={"documento_a": [], "documento_b": ["Erro de conteúdo no documento B."]},
    )
    assert document.find("textarea", name="documento_a")[0].text.removeprefix("\n") == original
    assert "aria-invalid" not in document.find(id="documento_a")[0].attrs
    assert document.find(id="documento_b")[0].attrs["aria-invalid"] == "true"
    assert "documento_b-erro" in document.find(id="documento_b")[0].attrs["aria-describedby"]
    assert (
        document.find(id="documento_b-erro")[0].text.strip() == "Erro de conteúdo no documento B."
    )
    summary = document.find("section", **{"aria-labelledby": "resumo-erros"})[0]
    assert summary.find("a")[0].attrs["href"] == "#documento_b"
    assert not document.find(id="resultado")
    assert document.find("title")[0].text == "Revise os documentos — Jaccard"


def test_global_error_is_rendered_with_recovery(render):
    _, document = render(erro_global="Mensagem global segura.")
    assert document.find(id="erro-global")
    assert "Mensagem global segura." in document.text
    assert any(link.text == "Voltar ao formulário" for link in document.find("a"))


@pytest.mark.parametrize("status", [400, 404, 405, 413, 415, 500])
def test_error_pages_have_status_and_recovery(render, status):
    _, document = render("error.html", status_code=status, erro_global="Falha genérica.")
    assert document.find("title")[0].text == f"Erro {status} — Jaccard"
    assert "Falha genérica." in document.text
    assert not document.find("textarea")
    recovery = [link for link in document.find("a") if link.text == "Voltar ao formulário"][0]
    assert recovery.attrs["href"] == "/"
    assert ("Insira os textos novamente." in document.text) == (status == 413)


def test_html_is_escaped_in_documents_words_and_errors(render, sample_result):
    attack = '</textarea><script>alert("teste")</script>'
    sample_result["exclusivas_a"]["palavras"] = [attack]
    html, document = render(
        documentos={"documento_a": attack, "documento_b": "válido"},
        erros_campos={"documento_a": [attack], "documento_b": []},
        resultado=sample_result,
    )
    assert not document.find("script")
    assert attack not in html
    assert "&lt;script&gt;" in html
    assert document.find("textarea", name="documento_a")[0].text.removeprefix("\n") == attack
    assert document.find("li")


def test_initial_form_result_and_learning_content_follow_reading_order(render, sample_result):
    _, document = render(resultado=sample_result)
    main = document.find("main")[0]
    sections = [
        child.attrs.get("id") for child in main.children if getattr(child, "tag", "") == "section"
    ]
    assert sections == ["comparacao", "resultado", "exemplo", "metodo", "limitacoes"]


def test_learning_content_and_privacy_are_visible_without_comparing(render):
    _, document = render()
    for section_id in ("exemplo", "metodo", "limitacoes"):
        assert document.find(id=section_id)
    for phrase in (
        "ordem das palavras",
        "frequência das repetições",
        "artigos e preposições",
        "Sinônimos, paráfrases e traduções",
        "documento muito maior",
        "não pesquisa fontes na internet",
        "limiar de plágio",
        "probabilidade de plágio",
        "Os textos são processados para esta comparação e não são armazenados pela aplicação.",
    ):
        assert phrase in document.text
    assert not document.find("script")
