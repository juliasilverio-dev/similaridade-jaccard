"""Entrada simples para a demonstração local: python backend/run.py."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
