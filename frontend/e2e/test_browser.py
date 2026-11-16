"""Aceite em navegador real, sempre com JavaScript da página desabilitado."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from app import routes

ARTIFACTS = Path(__file__).resolve().parents[1] / "test-results"


def compare(page, text_a, text_b):
    page.get_by_label("Documento A", exact=True).fill(text_a)
    page.get_by_label("Documento B", exact=True).fill(text_b)
    with page.expect_navigation() as navigation:
        page.get_by_role("button", name="Comparar documentos").click()
    return navigation.value


def assert_no_horizontal_overflow(page):
    dimensions = page.evaluate("""() => ({
        client: document.documentElement.clientWidth,
        scroll: document.documentElement.scrollWidth,
        overflowing: [...document.querySelectorAll('body *')].filter(element =>
            element.getBoundingClientRect().right > innerWidth + 1 ||
            element.scrollWidth > element.clientWidth + 1
        ).slice(0, 10).map(element => ({
            tag: element.tagName, id: element.id, className: element.className,
            right: element.getBoundingClientRect().right,
            scroll: element.scrollWidth, client: element.clientWidth
        }))
    })""")
    assert dimensions["scroll"] <= dimensions["client"], json.dumps(dimensions, indent=2)


def test_example_comparison_and_clear_work_without_javascript(page):
    page.get_by_role("link", name="Carregar exemplo").click()
    expect(page.locator("#resultado")).to_have_count(0)
    expect(page.get_by_label("Documento A", exact=True)).to_have_value(
        "O aluno estuda Python e desenvolve sistemas."
    )
    page.get_by_role("button", name="Comparar documentos").click()
    expect(page.locator("#resultado .score")).to_have_text("75,00%")
    expect(page.locator("#resultado .calculation")).to_have_text("6 / 8 = 75,00%")
    expect(page.locator('[aria-labelledby="grupo-intersecao"] .words li')).to_have_count(6)
    expect(page.locator("#resultado")).to_contain_text("não comprova plágio")
    ARTIFACTS.mkdir(exist_ok=True)
    page.locator("#resultado").screenshot(path=str(ARTIFACTS / "resultado-desktop.png"))
    page.get_by_role("link", name="O método", exact=True).click()
    expect(page.locator("#resultado .score")).to_have_text("75,00%")
    page.get_by_role("link", name="Limpar comparação").click()
    expect(page.get_by_label("Documento A", exact=True)).to_have_value("")
    expect(page.get_by_label("Documento B", exact=True)).to_have_value("")
    expect(page.locator("#resultado")).to_have_count(0)


@pytest.mark.parametrize(
    ("text_a", "text_b", "score"),
    [
        ("Casa casa!", "CASA", "100,00%"),
        ("casa", "livro", "0,00%"),
    ],
)
def test_extremes_render_and_allow_another_comparison(page, text_a, text_b, score):
    assert compare(page, text_a, text_b).status == 200
    expect(page.locator("#resultado .score")).to_have_text(score)
    assert compare(page, "a b", "b c").status == 200
    expect(page.locator("#resultado .score")).to_have_text("33,33%")


def test_native_required_and_server_errors_preserve_other_field(page):
    page.get_by_role("button", name="Comparar documentos").click()
    expect(page.get_by_label("Documento A", exact=True)).to_be_focused()
    expect(page.locator("#resultado")).to_have_count(0)
    assert compare(page, "!!!", "Texto B preservado.").status == 422
    expect(page.get_by_label("Documento B", exact=True)).to_have_value("Texto B preservado.")
    expect(page.locator("#resumo-erros")).to_have_text("Revise os documentos informados")
    expect(page.get_by_label("Documento A", exact=True)).to_have_attribute("aria-invalid", "true")
    page.locator('.error-summary a[href="#documento_a"]').click()
    expect(page.get_by_label("Documento A", exact=True)).to_be_focused()
    expect(page.locator("#resultado")).to_have_count(0)
    assert compare(page, " \n ", "válido").status == 422


def test_long_document_is_truncated_with_explicit_notice(page):
    assert compare(page, "a" * 100_001, "Texto preservado.").status == 422
    expect(page.get_by_label("Documento A", exact=True)).to_have_value("a" * 100_000)
    expect(page.get_by_label("Documento B", exact=True)).to_have_value("Texto preservado.")
    expect(page.locator("#documento_a-erro")).to_contain_text("primeiros 100.000 caracteres")


def test_keyboard_can_complete_comparison(page):
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#conteudo")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.get_by_label("Documento A", exact=True)).to_be_focused()
    page.keyboard.type("casa azul")
    page.keyboard.press("Tab")
    expect(page.get_by_label("Documento B", exact=True)).to_be_focused()
    page.keyboard.type("casa verde")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Comparar documentos")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#resultado .score")).to_have_text("33,33%")


def test_html_and_leading_newline_remain_literal_and_private(page, live_url):
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    text = '\n</textarea><script>alert("teste")</script>\n'
    assert compare(page, text, "texto válido").status == 200
    expect(page.get_by_label("Documento A", exact=True)).to_have_value(text)
    # O antivírus do host pode inserir uma referência de script externo no HTML
    # recebido pelo Chrome. Não alterar o antivírus: os testes de template já
    # verificam que a aplicação não gera scripts. Aqui a entrada não pode criar
    # um script inline nem escapar do campo de texto.
    expect(page.locator("script:not([src])")).to_have_count(0)
    assert all(url.startswith(live_url) for url in requests)
    assert all("script" not in url and "texto" not in url for url in requests)
    assert page.context.cookies() == []


@pytest.mark.parametrize("width", [320, 768, 1280])
def test_responsive_layout_and_long_word_groups(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    a = page.get_by_label("Documento A", exact=True).bounding_box()
    b = page.get_by_label("Documento B", exact=True).bounding_box()
    assert a and b
    if width <= 768:
        assert b["y"] > a["y"] + a["height"]
    else:
        assert abs(a["y"] - b["y"]) < 1
    assert_no_horizontal_overflow(page)
    ARTIFACTS.mkdir(exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"inicio-{width}.png"))
    shared = " ".join(f"comum{i}" for i in range(55))
    long_word = "palavra" * 500
    compare(page, f"{shared} {long_word}", shared)
    expect(page.locator("#resultado")).to_contain_text(
        "Exibindo 50 de 55 palavras; 5 não exibidas."
    )
    assert_no_horizontal_overflow(page)
    page.evaluate("document.documentElement.style.zoom = '2'")
    assert_no_horizontal_overflow(page)
    expect(page.get_by_role("button", name="Comparar documentos")).to_be_enabled()


@pytest.mark.parametrize(("path", "status"), [("/inexistente", 404), ("/comparar", 405)])
def test_error_pages_offer_recovery(page, live_url, path, status):
    response = page.goto(live_url + path)
    assert response.status == status
    expect(page.get_by_role("heading", level=2)).to_contain_text(str(status))
    page.get_by_role("link", name="Voltar ao formulário").click()
    expect(page.get_by_label("Documento A", exact=True)).to_have_value("")


def test_oversized_http_body_displays_recovery_page(page):
    large_body = "documento_a=a&documento_b=" + "x" * (2 * 1024 * 1024)
    page.route("**/comparar", lambda route: route.continue_(post_data=large_body))
    assert compare(page, "a", "a").status == 413
    expect(page.get_by_role("heading", level=2)).to_contain_text("413")
    expect(page.locator("main")).to_contain_text("Insira os textos novamente.")
    expect(page.get_by_role("link", name="Voltar ao formulário")).to_be_visible()


def test_internal_error_does_not_display_document(page, monkeypatch):
    secret = "CONTEUDO_PRIVADO_TESTE"

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(routes, "compare_stats", fail)
    assert compare(page, secret, "válido").status == 500
    expect(page.locator("main")).not_to_contain_text(secret)
    expect(page.get_by_role("link", name="Voltar ao formulário")).to_be_visible()
