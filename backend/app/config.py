"""Limites do comparador. Flask lê as constantes em letras maiúsculas."""

MAX_DOCUMENT_CHARACTERS = 100_000
MAX_DISPLAYED_WORDS = 50
MAX_REQUEST_BYTES = 2 * 1024 * 1024


MAX_CONTENT_LENGTH = MAX_REQUEST_BYTES
# O parser de formulário usa o mesmo limite total, inclusive para textos Unicode.
MAX_FORM_MEMORY_SIZE = MAX_REQUEST_BYTES
