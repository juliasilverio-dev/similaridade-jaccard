"""Fixtures locais: testes não abrem servidor nem utilizam serviços externos."""

import pytest
from flask import template_rendered

from app import create_app


@pytest.fixture
def app():
    return create_app({"TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def rendered(app):
    templates = []

    def record(sender, template, context, **extra):
        templates.append((template.name, context))

    with template_rendered.connected_to(record, app):
        yield templates
