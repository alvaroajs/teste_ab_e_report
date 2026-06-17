"""
Fluxo:
  1. Lê o JSON `_resumo_completo.json` do pipeline de análise.
  2. Lê o template do prompt em `prompts/prompt_gemini.md`.
  3. Substitui os placeholders <<<...>>> com os dados do parceiro.
  4. Chama a API Gemini com retry automático.
  5. Converte a resposta Markdown → PDF profissional (WeasyPrint).

Uso standalone:
  python src/gemini_report.py --json outputs/parceiro_a_resumo_completo.json
  python src/gemini_report.py --all
  python src/gemini_report.py --json ... --model gemini-2.5-flash --no-pdf

Variáveis de ambiente (arquivo .env na raiz do projeto):
  GEMINI_API_KEY=sua_chave_aqui
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

from config import OUTPUTS_DIR

DEFAULT_MODEL       = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.3
MAX_RETRIES         = 3
RETRY_DELAY_S       = 8
PROMPT_TEMPLATE_PATH = ROOT_DIR / "prompts" / "prompt_gemini.md"
REPORTS_OUT_DIR      = ROOT_DIR / "reports" / "gemini"

logger = logging.getLogger(__name__)

def load_and_trim_json(json_path: str | Path) -> tuple[dict, str, list[str]]:
    """
    Lê o JSON do pipeline e reconstrói um payload ultra-reduzido contendo
    apenas as estatísticas agregadas e comparações estatísticas necessárias.
    Reduz o payload de 155KB para <1.5KB, diminuindo drasticamente os tokens
    de prompt e liberando contexto para a geração completa do PDF (evitando truncamento).
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON não encontrado: {json_path}")

    with open(path, encoding="utf-8") as f:
        original_data = json.load(f)

    metadata = original_data.get("metadata", {})
    parceiro = metadata.get("parceiro", path.stem.split("_")[0])
    chart_paths = original_data.get("charts", [])

    # Monta a estrutura compacta
    trimmed_data = {
        "metadata": {
            "parceiro": parceiro,
            "periodo_inicio": metadata.get("periodo_inicio", "N/A")[:10],
            "periodo_fim": metadata.get("periodo_fim", "N/A")[:10],
            "total_observacoes": metadata.get("total_observacoes", "N/A"),
            "grupo_controle": metadata.get("grupo_controle", "Grupo 1"),
            "alpha": metadata.get("alpha", 0.05),
            "nivel_confianca": metadata.get("nivel_confianca", 0.95),
            "grupos": metadata.get("grupos", [])
        },
        "desempenho_grupos": {},
        "comparacoes_vs_controle": {}
    }

    # 1. Agrega apenas média e soma por grupo e métrica
    for grupo_nome, grupo_info in original_data.get("grupos", {}).items():
        trimmed_data["desempenho_grupos"][grupo_nome] = {}
        for metrica_nome, metrica_info in grupo_info.get("metricas", {}).items():
            desc = metrica_info.get("descritiva", {})
            media = desc.get("media", None)
            soma = desc.get("soma", None)
            
            trimmed_data["desempenho_grupos"][grupo_nome][metrica_nome] = {
                "media": round(media, 2) if isinstance(media, (int, float)) else media,
                "soma": round(soma, 2) if isinstance(soma, (int, float)) else soma
            }

    # 2. Agrega apenas p-value, significância e uplift para as variantes vs controle
    for comp in original_data.get("comparacoes", []):
        var_nome = comp.get("grupo_variante")
        metrica_nome = comp.get("metrica")
        if not var_nome or not metrica_nome:
            continue
            
        if var_nome not in trimmed_data["comparacoes_vs_controle"]:
            trimmed_data["comparacoes_vs_controle"][var_nome] = {}

        # Prioriza o p-value do t-teste, se não houver usa mann_whitney
        ttest = comp.get("ttest", {})
        p_val = ttest.get("p_value", None)
        sig = ttest.get("significativo", None)
        if p_val is None:
            mw = comp.get("mann_whitney", {})
            p_val = mw.get("p_value", None)
            sig = mw.get("significativo", None)

        uplift_pct = comp.get("uplift", {}).get("relativo_pct", None)

        trimmed_data["comparacoes_vs_controle"][var_nome][metrica_nome] = {
            "p_value": round(p_val, 6) if isinstance(p_val, (int, float)) else p_val,
            "significativo": sig,
            "uplift_pct": round(uplift_pct, 2) if isinstance(uplift_pct, (int, float)) else uplift_pct
        }

    size_kb = len(json.dumps(trimmed_data)) / 1024
    logger.info("JSON carregado e compactado de forma agressiva: %s (%.1f KB após compressão)", path.name, size_kb)
    return trimmed_data, parceiro, chart_paths

def load_prompt_template(template_path: Path = PROMPT_TEMPLATE_PATH) -> str:
    """
    Lê o arquivo de template do prompt em Markdown.

    Raises FileNotFoundError se o arquivo não existir.
    """
    if not template_path.exists():
        raise FileNotFoundError(
            f"Template de prompt não encontrado: {template_path}\n"
            f"   Esperado em: {PROMPT_TEMPLATE_PATH}"
        )
    return template_path.read_text(encoding="utf-8")

def build_prompt(data: dict, parceiro: str, chart_paths: list[str], template: str | None = None) -> str:
   
    if template is None:
        template = load_prompt_template()

    meta = data.get("metadata", {})

    md_charts = []
    for cp in chart_paths:
        name = Path(cp).name
        # Tenta inferir o título a partir do nome do arquivo
        title = name.replace(parceiro.lower().replace(" ", "_"), "").replace("_", " ").strip().title()
        title = title.replace(".Png", "").replace(".Jpg", "")
        # O WeasyPrint processa imagens com caminhos relativos ao `base_url` (que é a raiz)
        try:
            rel_path = Path(cp).relative_to(ROOT_DIR)
            md_charts.append(f"![{title}]({rel_path.as_posix()})")
        except ValueError:
            md_charts.append(f"![{title}](charts/{name})")
        
    charts_markdown = "\n\n".join(md_charts) if md_charts else "Nenhum gráfico gerado."

    replacements = {
        "<<<parceiro>>>":       parceiro,
        "<<<periodo_inicio>>>": meta.get("periodo_inicio", "N/A")[:10],
        "<<<periodo_fim>>>":    meta.get("periodo_fim", "N/A")[:10],
        "<<<grupos>>>":         ", ".join(meta.get("grupos", [])),
        "<<<grupo_controle>>>": meta.get("grupo_controle", "Grupo 1"),
        "<<<total_obs>>>":      str(meta.get("total_observacoes", "N/A")),
        "<<<alpha>>>":          str(meta.get("alpha", 0.05)),
        "<<<confidence>>>":     str(int(meta.get("nivel_confianca", 0.95) * 100)),
        "<<<charts_markdown>>>": charts_markdown,
        "<<<chart_1>>>":        md_charts[0] if len(md_charts) > 0 else "Nenhum gráfico gerado.",
        "<<<chart_2>>>":        md_charts[1] if len(md_charts) > 1 else "",
        "<<<json_payload>>>":   json.dumps(data, ensure_ascii=False, indent=2),
    }

    prompt = template
    for marker, value in replacements.items():
        prompt = prompt.replace(marker, value)

    prompt = re.sub(r"<!--.*?-->", "", prompt, flags=re.DOTALL).strip()

    return prompt

def call_gemini(
    prompt: str,
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    chart_paths: list[str] | None = None,
) -> str:
    """
    Envia o prompt ao Gemini e retorna a resposta em Markdown.

    Implementa retry com backoff para:
    - 429 RESOURCE_EXHAUSTED (rate limit)
    - 503 SERVICE_UNAVAILABLE

    Raises
    ------
    EnvironmentError : GEMINI_API_KEY ausente ou sem cota.
    ValueError       : Requisição inválida (ex: excesso de tokens).
    RuntimeError     : Todas as tentativas falharam.
    """
    try:
        from google import genai
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError(
            "❌ Biblioteca 'google-genai' não instalada.\n"
            "   Execute: pip install google-genai"
        )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "❌ GEMINI_API_KEY não encontrada.\n"
            "   1. Crie um arquivo .env na raiz do projeto:\n"
            "      GEMINI_API_KEY=sua_chave_aqui\n"
            "   2. Obtenha sua chave gratuita em: https://aistudio.google.com/app/apikey"
        )

    client = genai.Client(api_key=api_key)

    contents = [prompt]
    if chart_paths:
        for cp in chart_paths:
            path = Path(cp)
            if path.exists():
                try:
                    contents.append(genai_types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type="image/png" if path.suffix.lower() == ".png" else "image/jpeg"
                    ))
                    logger.info("Imagem anexada à chamada do Gemini: %s", path.name)
                except Exception as img_err:
                    logger.warning("Falha ao carregar imagem %s para o Gemini: %s", path.name, img_err)

    generate_config = genai_types.GenerateContentConfig(
        temperature=temperature,
        safety_settings=[
            genai_types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_ONLY_HIGH",
            ),
            genai_types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_ONLY_HIGH",
            ),
        ],
    )

    last_error: Exception | None = None

    current_model = model_name
    for attempt in range(1, MAX_RETRIES + 1):

        try:
            logger.info(
                "Chamando Gemini (%s) — tentativa %d/%d…",
                current_model, attempt, MAX_RETRIES,
            )
            t0 = time.time()

            response = client.models.generate_content(
                model=current_model,
                contents=contents,
                config=generate_config,
            )
            elapsed = time.time() - t0

            if not response.text:
                finish = (
                    response.candidates[0].finish_reason
                    if response.candidates else "desconhecido"
                )
                raise RuntimeError(f"Resposta vazia. Finish reason: {finish}")

            if len(response.text) < 200:
                raise ValueError(f"Resposta muito curta ({len(response.text)} caracteres). Tentando novamente...")

            logger.info(
                "✅ Resposta recebida em %.1fs (%d caracteres).",
                elapsed, len(response.text),
            )
            return response.text

        except genai_errors.ClientError as e:
            status   = getattr(e, "status_code", None) or getattr(e, "code", None)
            err_str  = str(e)

            if status == 429:
                if "limit: 0" in err_str or "free_tier" in err_str.lower():
                    raise EnvironmentError(
                        "❌ Chave sem cota no free tier (limit: 0) contate o adiministrador.\n"
                        "   Crie uma nova chave em https://aistudio.google.com/app/apikey\n"
                        "   Clique em 'Create API key in new project'."
                    ) from e
                wait = RETRY_DELAY_S * attempt
                logger.warning(
                    "⚠️  Rate limit (tentativa %d/%d). Aguardando %ds…",
                    attempt, MAX_RETRIES, wait,
                )
                last_error = e
                time.sleep(wait)

            elif status == 400:
                if "API_KEY_INVALID" in err_str or "key expired" in err_str.lower():
                    raise EnvironmentError(
                        f"❌ Chave de API inválida ou expirada.\n"
                        f"   Gere uma nova em: https://aistudio.google.com/app/apikey"
                    ) from e
                raise ValueError(
                    f"❌ Requisição inválida (possível excesso de tokens): {err_str[:300]}"
                ) from e

            else:
                logger.warning(
                    "⚠️  Erro do cliente (status=%s, tentativa %d/%d): %s",
                    status, attempt, MAX_RETRIES, err_str[:120],
                )
                last_error = e
                time.sleep(RETRY_DELAY_S)

        except genai_errors.ServerError as e:
            logger.warning(
                "⚠️  Serviço indisponível (tentativa %d/%d). Aguardando %ds…",
                attempt, MAX_RETRIES, RETRY_DELAY_S,
            )
            last_error = e
            time.sleep(RETRY_DELAY_S)

        except Exception as e:
            logger.error("❌ Erro inesperado: %s", e)
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)

    # Se todas as tentativas falharam, verifica se foi erro de congestionamento/serviço (503)
    err_str = str(last_error) if last_error else ""
    is_503 = False
    if last_error:
        status_code = getattr(last_error, "status_code", None) or getattr(last_error, "code", None)
        if status_code == 503:
            is_503 = True
    if "503" in err_str or "unavailable" in err_str.lower() or "experiencing high demand" in err_str.lower() or "try again later" in err_str.lower():
        is_503 = True

    if is_503:
        raise RuntimeError(
            "⚠️ Os servidores do Gemini estão temporariamente congestionados devido à alta demanda. "
            "Por favor, aguarde alguns instantes e tente rodar a análise novamente."
        ) from last_error

    raise RuntimeError(
        f"❌ Todas as {MAX_RETRIES} tentativas falharam. Último erro: {last_error}"
    )

PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --color-bg:       #ffffff;
    --color-text:     #1a1a2e;
    --color-accent:   #16213e;
    --color-primary:  #0f3460;
    --color-highlight:#e94560;
    --color-border:   #e2e8f0;
    --color-muted:    #64748b;
    --color-code-bg:  #f8fafc;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: var(--color-text);
    background: var(--color-bg);
}

@page {
    size: A4;
    margin: 1.6cm 2.0cm 1.6cm 2.0cm;
    @bottom-center {
        content: "Confidencial — Página " counter(page) " de " counter(pages);
        font-size: 7.5pt;
        color: var(--color-muted);
    }
    @top-right {
        content: "Relatório Executivo A/B";
        font-size: 7.5pt;
        color: var(--color-muted);
    }
}

@page :first {
    @bottom-center {
        content: "";
    }
    @top-right {
        content: "";
    }
}

h1 {
    font-size: 16pt; font-weight: 700; color: var(--color-primary);
    border-bottom: 2.5px solid var(--color-highlight);
    padding-bottom: 0.3em; margin: 0 0 0.8em 0;
}
h2 {
    font-size: 12pt; font-weight: 600; color: var(--color-accent);
    border-left: 3.5px solid var(--color-primary);
    padding-left: 0.6em; margin: 1.2em 0 0.6em 0;
    page-break-after: avoid;
}
h3 {
    font-size: 10pt; font-weight: 600; color: var(--color-primary);
    margin: 1.0em 0 0.4em 0; page-break-after: avoid;
}
h4 {
    font-size: 9pt; font-weight: 600; color: var(--color-muted);
    text-transform: uppercase; letter-spacing: 0.05em; margin: 0.8em 0 0.3em 0;
}

img {
    max-width: 85%;
    max-height: 5.0cm;
    object-fit: contain;
    display: block;
    margin: 0.6em auto;
    border-radius: 6px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    border: 1px solid var(--color-border);
    page-break-inside: avoid;
    break-inside: avoid;
}

p { margin: 0.3em 0 0.5em 0; text-align: justify; hyphens: auto; }

table { width: 100%; border-collapse: collapse; margin: 0.8em 0 1.2em 0; font-size: 8pt; page-break-inside: avoid; }
thead tr { background: var(--color-primary); color: white; }
thead th { padding: 0.4em 0.6em; text-align: left; font-weight: 600; font-size: 8pt; }
tbody tr:nth-child(even) { background: #f0f4f8; }
tbody tr:nth-child(odd)  { background: #ffffff; }
tbody td { padding: 0.3em 0.6em; border-bottom: 1px solid var(--color-border); vertical-align: top; }

pre, code { font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 7.5pt; }
pre {
    background: var(--color-code-bg); border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-primary); border-radius: 6px;
    padding: 0.8em 1.0em; margin: 0.6em 0 1.0em 0; page-break-inside: avoid;
    white-space: pre-wrap; word-wrap: break-word;
}
code { background: var(--color-code-bg); padding: 0.1em 0.3em; border-radius: 3px; color: var(--color-highlight); }
pre code { background: transparent; padding: 0; color: var(--color-text); }

ul, ol { margin: 0.4em 0 0.6em 1.2em; }
li { margin: 0.15em 0; line-height: 1.45; }

blockquote {
    border-left: 4px solid var(--color-highlight); background: #fff7f7;
    padding: 0.6em 1.0em; margin: 0.8em 0; border-radius: 0 6px 6px 0;
    font-style: italic; color: var(--color-accent);
}
hr { border: none; border-top: 2px solid var(--color-border); margin: 1.0em 0; }
strong { font-weight: 600; color: var(--color-accent); }
em { color: var(--color-muted); }

/* Classes adicionais para paginação e capa */
.page-break {
    page-break-before: always;
    clear: both;
}
.cover-page {
    text-align: center;
    padding: 3cm 1cm 1.5cm 1cm;
}
.cover-title {
    font-size: 22pt;
    font-weight: 700;
    color: var(--color-primary);
    margin-bottom: 0.3em;
    line-height: 1.2;
}
.cover-subtitle {
    font-size: 12pt;
    color: var(--color-muted);
    margin-bottom: 2.5em;
}
.cover-meta {
    font-size: 9pt;
    margin-top: 2cm;
    border-top: 2px solid var(--color-primary);
    padding-top: 1.0em;
    line-height: 1.6;
}
"""

HTML_WRAPPER = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""

def markdown_to_pdf(markdown_text: str, output_path: Path, parceiro: str) -> bool:
    """
    Converte Markdown → HTML → PDF.

    Tenta WeasyPrint primeiro, faz fallback para pdfkit.
    Não salva o .md em disco, apenas processa em memória para PDF.

    Retorna True se o PDF foi gerado.
    """
    try:
        import markdown as md_lib
    except ImportError:
        logger.error("❌ 'markdown' não instalado. Execute: pip install markdown")
        return False

    extensions = [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.toc",
        "markdown.extensions.nl2br",
        "markdown.extensions.sane_lists",
    ]
    html_body = md_lib.markdown(markdown_text, extensions=extensions)
    html_full = HTML_WRAPPER.format(
        title=f"Relatório Executivo A/B — {parceiro}",
        css=PDF_CSS,
        body=html_body,
    )

    try:
        from weasyprint import HTML as WeasyprintHTML
        WeasyprintHTML(string=html_full, base_url=str(ROOT_DIR)).write_pdf(str(output_path))
        logger.info("✅ PDF gerado com WeasyPrint: %s", output_path)
        return True
    except ImportError:
        logger.warning(
            "⚠️  WeasyPrint não instalado.\n"
            "   sudo apt-get install libcairo2 libpango-1.0-0 libpangocairo-1.0-0\n"
            "   pip install weasyprint"
        )
    except Exception as e:
        logger.warning("⚠️  WeasyPrint falhou: %s. Tentando pdfkit…", e)

    try:
        import pdfkit
        html_tmp = output_path.with_suffix(".tmp.html")
        html_tmp.write_text(html_full, encoding="utf-8")
        pdfkit.from_file(
            str(html_tmp), str(output_path),
            options={"page-size": "A4", "encoding": "UTF-8",
                     "margin-top": "22mm", "margin-bottom": "22mm",
                     "margin-left": "25mm", "margin-right": "25mm"},
        )
        html_tmp.unlink(missing_ok=True)
        logger.info("✅ PDF gerado com pdfkit: %s", output_path)
        return True
    except ImportError:
        logger.error("❌ Nem WeasyPrint nem pdfkit disponíveis. PDF não gerado.")
    except Exception as e:
        logger.error("❌ pdfkit falhou: %s", e)

    logger.error("Falha ao gerar o PDF.")
    return False

def process_json_file(
    json_path: str | Path,
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    generate_pdf: bool = True,
    out_dir: Path = REPORTS_OUT_DIR,
    prompt_template: str | None = None,
) -> dict:
    """
    Pipeline completo para um único arquivo JSON.

    Parâmetros
    ----------
    json_path       : Caminho para o JSON do pipeline de análise.
    model_name      : Modelo Gemini.
    temperature     : Temperatura de geração (0 = determinístico).
    generate_pdf    : Se False, salva só o Markdown.
    out_dir         : Diretório de saída.
    prompt_template : String do template (lido do arquivo se None).

    Retorna
    -------
    dict com keys: json_path, parceiro, sucesso, outputs, erro
    """
    result: dict = {
        "json_path": str(json_path),
        "parceiro":  None,
        "sucesso":   False,
        "outputs":   {},
        "erro":      None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Carrega e trimma o JSON
        data, parceiro, chart_paths = load_and_trim_json(json_path)
        result["parceiro"] = parceiro
        slug = parceiro.lower().replace(" ", "_")

        # 2. Monta o prompt
        logger.info("[%s] Montando prompt…", parceiro)
        prompt = build_prompt(data, parceiro, chart_paths, template=prompt_template)

        # 3. Chama a API


        logger.info("[%s] Enviando para Gemini (%s)…", parceiro, model_name)
        markdown_report = call_gemini(prompt, model_name, temperature, chart_paths=chart_paths)

        parts = parceiro.split(' ')
        if len(parts) == 2 and parts[0].lower() == "parceiro":
            pdf_filename = f"relatori_parceiro_{parts[1]}.pdf"
        else:
            pdf_filename = f"relatori_{slug}.pdf"
        pdf_path = out_dir / pdf_filename
        pdf_ok = False

        if generate_pdf:
            pdf_ok = markdown_to_pdf(markdown_report, pdf_path, parceiro)
            if pdf_ok:
                result["outputs"]["relatorio_pdf"] = str(pdf_path)
        else:
            # Se a geração de PDF estiver explicitamente desativada (ex: CLI --no-pdf), salva o Markdown
            md_path = pdf_path.with_suffix(".md")
            md_path.write_text(markdown_report, encoding="utf-8")
            result["outputs"]["relatorio_md"] = str(md_path)

        result["sucesso"] = True if (pdf_ok or not generate_pdf) else False

    except (FileNotFoundError, EnvironmentError, ValueError, RuntimeError) as e:
        result["erro"] = str(e)
        logger.error("❌ %s", e)
    except Exception as e:
        import traceback
        result["erro"] = f"{type(e).__name__}: {e}"
        logger.error("❌ Erro inesperado: %s\n%s", e, traceback.format_exc())

    return result

def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera relatórios executivos PDF de Testes A/B via Google Gemini.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python src/gemini_report.py --json outputs/parceiro_a_resumo_completo.json
  python src/gemini_report.py --all
  python src/gemini_report.py --json ... --model gemini-2.5-flash --no-pdf
  python src/gemini_report.py --all --out-dir relatorios/

Também pode ser acionado pelo pipeline principal:
  python src/main.py --gemini
  python src/main.py --gemini --file datasets/parceiro_a.csv

Variável de ambiente obrigatória:
  GEMINI_API_KEY  → arquivo .env na raiz do projeto
        """,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--json", metavar="CAMINHO",
                      help="Caminho para um único arquivo JSON.")
    mode.add_argument("--all", action="store_true",
                      help=f"Processa todos os *_resumo_completo.json em {OUTPUTS_DIR}/.")

    parser.add_argument("--model",       default=DEFAULT_MODEL,
                        help=f"Modelo Gemini (padrão: {DEFAULT_MODEL}).")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE,
                        help="Temperatura 0.0-1.0 (padrão: 0.3).")
    parser.add_argument("--no-pdf",      action="store_true",
                        help="Gera apenas o Markdown, sem PDF.")
    parser.add_argument("--out-dir",     default=str(REPORTS_OUT_DIR),
                        help=f"Diretório de saída (padrão: {REPORTS_OUT_DIR}).")
    parser.add_argument("--delay",       type=float, default=5.0,
                        help="Pausa em segundos entre parceiros (padrão: 5s).")
    parser.add_argument("--prompt",      default=str(PROMPT_TEMPLATE_PATH),
                        help=f"Template do prompt .md (padrão: {PROMPT_TEMPLATE_PATH}).")
    return parser

def main() -> None:
    parser = _build_cli_parser()
    args   = parser.parse_args()

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    out_dir      = Path(args.out_dir)
    generate_pdf = not args.no_pdf

    prompt_template = load_prompt_template(Path(args.prompt))

    if args.json:
        json_files = [args.json]
    else:
        json_files = sorted(Path(OUTPUTS_DIR).glob("*_resumo_completo.json"))
        if not json_files:
            logger.error("Nenhum *_resumo_completo.json encontrado em '%s'.", OUTPUTS_DIR)
            sys.exit(1)
        json_files = [str(f) for f in json_files]

    if not os.getenv("GEMINI_API_KEY", "").strip():
        logger.error(
            "❌ GEMINI_API_KEY não definida!\n"
            "   Crie .env na raiz com: GEMINI_API_KEY=sua_chave\n"
            "   Obtenha gratuitamente em: https://aistudio.google.com/app/apikey"
        )
        sys.exit(1)

    logger.info("Arquivos a processar: %d", len(json_files))

    all_results: list[dict] = []
    for i, json_path in enumerate(json_files):
        if i > 0:
            logger.info("Aguardando %.1fs…", args.delay)
            time.sleep(args.delay)

        result = process_json_file(
            json_path=json_path,
            model_name=args.model,
            temperature=args.temperature,
            generate_pdf=generate_pdf,
            out_dir=out_dir,
            prompt_template=prompt_template,
        )
        all_results.append(result)

    print("\n" + "━" * 60)
    print("  SUMÁRIO — RELATÓRIOS GEMINI")
    print("━" * 60)
    n_ok = sum(1 for r in all_results if r["sucesso"])
    for r in all_results:
        status = "✅" if r["sucesso"] else "❌"
        print(f"\n  {status} {r['parceiro'] or r['json_path']}")
        if r["sucesso"]:
            for k, v in r["outputs"].items():
                print(f"     📄 {k}: {Path(v).name}")
        else:
            print(f"     Erro: {r['erro']}")
    print(f"\n  Total: {n_ok}/{len(all_results)} relatório(s) gerado(s).")
    print("━" * 60 + "\n")

    sys.exit(0 if n_ok == len(all_results) else 1)

if __name__ == "__main__":
    main()
