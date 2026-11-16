"""Criação do Flask, limites de envio e páginas de erro."""

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.routes import page_context, web

REQUEST_TOO_LARGE_MESSAGE = (
    "Os textos enviados excedem o tamanho total permitido. Reduza-os e tente novamente."
)
ERROR_MESSAGES = {
    400: "Não foi possível interpretar a solicitação. Volte ao formulário e tente novamente.",
    404: "O endereço solicitado não existe.",
    405: "Este método não é permitido para o endereço solicitado.",
    413: REQUEST_TOO_LARGE_MESSAGE,
    415: "Envie os documentos pelo formulário de texto da aplicação.",
    500: "Não foi possível concluir a comparação. Volte ao formulário e tente novamente.",
}


class SafeFlask(Flask):
    def log_exception(self, exc_info) -> None:
        # O logger padrão inclui a mensagem/traceback da exceção, que poderia
        # conter um documento. Registrar apenas o tipo permite detectar a falha.
        self.logger.error("Falha interna durante o processamento (%s).", exc_info[0].__name__)


def create_app(test_config: Mapping[str, Any] | None = None) -> Flask:
    frontend_root = Path(__file__).resolve().parents[2] / "frontend"
    app = SafeFlask(
        __name__,
        template_folder=str(frontend_root / "templates"),
        static_folder=str(frontend_root / "static"),
        static_url_path="/static",
    )
    app.config.from_object("app.config")
    if test_config is not None:
        app.config.update(test_config)

    app.register_blueprint(web)

    @app.errorhandler(HTTPException)
    def handle_error(error: HTTPException):
        status = error.code or 500
        message = ERROR_MESSAGES.get(status, "Não foi possível atender à solicitação.")
        # Mantém os cabeçalhos HTTP, como Allow para um método não permitido.
        response = error.get_response()
        response.set_data(
            render_template("error.html", **page_context(erro_global=message), status_code=status)
        )
        response.content_type = "text/html; charset=utf-8"
        return response

    @app.before_request
    def enforce_request_limit() -> None:
        limit = app.config["MAX_CONTENT_LENGTH"]
        if limit is None:
            return
        length = request.content_length
        if length is not None and length > limit:
            raise RequestEntityTooLarge()
        if length is None and request.environ.get("wsgi.input_terminated"):
            # Alguns parsers encerram a leitura exatamente no limite e poderiam
            # aceitar silenciosamente um corpo truncado. Com término sinalizado
            # pelo servidor WSGI, leia até um byte extra para distinguir excesso
            # de uma entrada cujo tamanho é exatamente o limite.
            source = request.environ["wsgi.input"]
            body = bytearray()
            while len(body) <= limit:
                chunk = source.read(min(64 * 1024, limit + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            if len(body) > limit:
                raise RequestEntityTooLarge()
            request.environ["wsgi.input"] = BytesIO(body)
            request.environ["CONTENT_LENGTH"] = str(len(body))

    @app.after_request
    def protect_dynamic_responses(response):
        if request.endpoint != "static" or response.status_code >= 400:
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'none'; style-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app
