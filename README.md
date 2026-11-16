<div align="center">

`✦ ─── JACCARD // TEXT LAB ─── ✦`

# Similaridade de Jaccard

**Dois textos · conjuntos de palavras · um percentual**

`PYTHON` · `FLASK` · `HTML + CSS`

Projeto de comparação textual.

</div>

Compare dois textos e veja o percentual de similaridade, as palavras em comum e as exclusivas de cada documento. A aplicação usa Flask para processar o formulário e gerar o HTML, sem JavaScript ou banco de dados.

## Executar no Windows

Tenha **Python 3.12 ou superior** instalado e disponível pelo comando `python`. No PowerShell, dentro da pasta `similaridade-jaccard`, execute:

```powershell
.\iniciar.cmd
```

Se o terminal não reconhecer `python`, adicione a instalação do Python ao `PATH` e abra o PowerShell novamente.

Na primeira execução, o script cria o ambiente virtual e instala o Flask e suas dependências; essa etapa precisa de internet. Nas próximas, reutiliza o ambiente preparado.

Abra **http://127.0.0.1:5000** no navegador. Para encerrar, pressione `Ctrl+C` no terminal. O servidor é destinado à apresentação local.

## Como funciona

1. As palavras são normalizadas: maiúsculas e minúsculas são equivalentes, e pontuação e espaços separam palavras. Acentos e números são preservados.
2. Cada texto vira um conjunto de palavras distintas. Repetições não aumentam o peso de uma palavra.
3. O índice é o tamanho da **interseção** (palavras em comum) dividido pelo tamanho da **união** (todas as palavras distintas).

```text
J(A, B) = |A ∩ B| / |A ∪ B|
```

A opção **Carregar exemplo** preenche estes textos. Depois, clique em **Comparar documentos**:

```text
A: O aluno estuda Python e desenvolve sistemas.
B: O aluno estuda Python e cria sistemas.

Interseção: 6 palavras — aluno, e, estuda, o, python, sistemas
União: 8 palavras — as 6 em comum + desenvolve + cria
Resultado: 6 / 8 = 75,00%
```

Cada documento aceita até **100.000 caracteres** e precisa conter pelo menos uma palavra ou número. As listas exibem até 50 palavras por grupo; o cálculo considera todas.

**Limitação:** Jaccard compara vocabulário, sem entender significado, sinônimos, ordem ou frequência das palavras. Um resultado alto **não comprova plágio** nem indica a porcentagem copiada.

## Onde estudar o código

- [jaccard.py](backend/app/jaccard.py): `tokenize` extrai palavras, `analyze_text` cria os conjuntos e `compare_stats` calcula interseção (`&`), união (`|`) e percentual.
- [routes.py](backend/app/routes.py): `GET /` abre o formulário e `POST /comparar` recebe os textos e devolve o resultado. Também contém o exemplo.
- [validation.py](backend/app/validation.py) e [config.py](backend/app/config.py): validação das entradas e limites de tamanho.
- [__init__.py](backend/app/__init__.py): criação do Flask, configuração das pastas e tratamento de erros. [run.py](backend/run.py) inicia o servidor.
- [templates](frontend/templates) e [styles.css](frontend/static/css/styles.css): páginas HTML com Jinja e aparência da interface.

Para a apresentação, explique a fórmula, mostre o cálculo no código e execute o exemplo de 75%. Depois, demonstre textos iguais (100%), sem palavras em comum (0%) e uma entrada só com pontuação (erro).

## Testes

<details>
<summary>Comandos de desenvolvimento (opcional)</summary>

Depois de executar o projeto uma vez, encerre o servidor com `Ctrl+C`. Na raiz do projeto, rode:

```powershell
cd backend
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests ../frontend/tests --cov=app
```

O comando `ensurepip` prepara o pip caso o ambiente tenha sido criado sem ele, como pode ocorrer com uv.

Os testes verificam o cálculo, a normalização, os erros e a renderização das páginas. Para os testes de navegador, tenha Chrome instalado e execute, ainda em `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest ../frontend/e2e -c ../frontend/pyproject.toml
```

Para conferir o estilo do Python:

```powershell
.\.venv\Scripts\python.exe -m ruff check . ../frontend
.\.venv\Scripts\python.exe -m ruff format --check . ../frontend
```

O arquivo `backend/uv.lock` também está disponível para quem usa uv e deseja reproduzir as versões das dependências com `uv sync --locked` dentro de `backend`.

</details>

## Arquivos e GitHub

Mantenha `backend` e `frontend` lado a lado: o Flask serve as duas pastas em um único servidor.

Não é necessário `.env`, pois não há credenciais ou serviços externos. O `.gitignore` exclui o ambiente virtual, caches, relatórios de teste e eventuais arquivos `.env`. Os textos enviados não são armazenados pela aplicação.

<div align="center">

`✦ [ END OF FILE ] · feito para aprender ✦`

</div>
