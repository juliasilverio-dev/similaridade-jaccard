"""Chrome headless isolado e servidor Flask temporário para testes reais de UI."""

import os
from threading import Thread

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import create_app


@pytest.fixture(scope="session")
def live_url():
    app = create_app({"TESTING": True, "PROPAGATE_EXCEPTIONS": False})
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope="session")
def browser():
    channel = os.environ.get("JACCARD_BROWSER_CHANNEL", "chrome")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=None if channel == "chromium" else channel, headless=True
        )
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(browser, live_url):
    context = browser.new_context(
        java_script_enabled=False,
        viewport={"width": 1280, "height": 900},
        locale="pt-BR",
    )
    page = context.new_page()
    page.set_default_timeout(10_000)
    page.goto(live_url)
    try:
        yield page
    finally:
        context.close()
