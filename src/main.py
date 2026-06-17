"""
src/main.py

Fluxo de execução:
  1. Descoberta automática de datasets na pasta `datasets/`
  2. Para cada arquivo CSV encontrado:
     a. Pré-processamento e limpeza (analysis.py)
     b. Estatísticas descritivas (statistics.py)
     c. Testes de hipótese (statistics.py)
     d. Visualizações — boxplot, KDE, uplift, heatmap (visualizations.py)
     e. Exportação — CSV descritivo, CSV hipóteses, JSON completo (reporting.py)
  3. Consolidação cross-parceiro (sheets.py)
  4. [Opcional] Geração de relatórios executivos via Gemini (--gemini)
  5. Sumário final no terminal

"""

import argparse
import glob
import logging
import os
import sys
import time
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from config import (
    DATASETS_DIR,
    OUTPUTS_DIR,
    REPORTS_DIR,
    CHARTS_DIR,
    LOGS_DIR,
)
from src.analysis       import load_and_clean
from src.statistics     import compute_descriptive_stats, compute_hypothesis_tests
from src.visualizations import generate_all_charts
from src.reporting      import (
    export_csv_descriptive,
    export_csv_hypothesis,
    build_full_summary,
    export_json_full,
)
from src.sheets import consolidate_reports

def setup_logging(log_level: str = "INFO") -> None:
    """Configura logging para arquivo + console com formato rico."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, "pipeline.log")

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(numeric_level)
    ch.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[fh, ch])
    logging.info("Logging iniciado. Arquivo de log: %s", log_file)

def ensure_dirs() -> None:
    """Garante que todos os diretórios de saída existam."""
    for d in [DATASETS_DIR, OUTPUTS_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR]:
        os.makedirs(d, exist_ok=True)

def run_pipeline_for_file(filepath: str) -> dict:
    """
    
    Dicionário com resultado do processamento:
    {
      'arquivo': str,
      'parceiro': str,
      'sucesso': bool,
      'outputs': dict,
      'alertas': list,
      'erro': str | None,
      'tempo_s': float,
    }
    """
    logger = logging.getLogger(__name__)
    start = time.time()

    logger.info("=" * 60)
    logger.info("Processando: %s", filepath)
    logger.info("=" * 60)

    result = {
        "arquivo":  filepath,
        "parceiro": None,
        "sucesso":  False,
        "outputs":  {},
        "alertas":  [],
        "erro":     None,
        "tempo_s":  0.0,
    }

    try:
        df_clean, alerts = load_and_clean(filepath)
        result["alertas"] = alerts

        if "parceiro" in df_clean.columns and not df_clean["parceiro"].empty:
            parceiro = df_clean["parceiro"].mode()[0]
        else:
            parceiro = Path(filepath).stem
        result["parceiro"] = parceiro

        logger.info("[%s] Dados limpos: %d linhas.", parceiro, len(df_clean))
        if alerts:
            for a in alerts:
                logger.warning("[%s] ALERTA: %s", parceiro, a)

        descriptive_df = compute_descriptive_stats(df_clean, parceiro)

        hypothesis_df = compute_hypothesis_tests(df_clean, parceiro)

        chart_paths = generate_all_charts(df_clean, hypothesis_df, parceiro)

        path_desc_csv = export_csv_descriptive(descriptive_df, parceiro)
        path_hyp_csv  = export_csv_hypothesis(hypothesis_df, parceiro)

        summary = build_full_summary(
            df_clean=df_clean,
            descriptive_df=descriptive_df,
            hypothesis_df=hypothesis_df,
            parceiro=parceiro,
            alerts=alerts,
            chart_paths=chart_paths,
        )
        path_json = export_json_full(summary, parceiro)

        result["sucesso"] = True
        result["outputs"] = {
            "csv_descritivo":  path_desc_csv,
            "csv_hipoteses":   path_hyp_csv,
            "json_completo":   path_json,
            "graficos":        chart_paths,
        }
        result["summary"] = summary



        result["_descriptive_df"] = descriptive_df
        result["_hypothesis_df"]  = hypothesis_df

        logger.info(
            "[%s] Pipeline concluído em %.1fs. Outputs: %d arquivos.",
            parceiro, time.time() - start, len(chart_paths) + 3,
        )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        result["erro"] = error_msg
        logger.error(
            "Erro fatal no pipeline para '%s': %s\n%s",
            filepath, error_msg, traceback.format_exc(),
        )

    result["tempo_s"] = round(time.time() - start, 2)
    return result

def discover_datasets(directory: str) -> list[str]:
    """
    Descobre todos os arquivos CSV na pasta `datasets/`.

    Parâmetros
    ----------
    directory : Caminho para a pasta de datasets.

    Retorna
    -------
    Lista de caminhos absolutos dos CSVs encontrados.
    """
    pattern = os.path.join(directory, "*.csv")
    files = sorted(glob.glob(pattern))
    logging.getLogger(__name__).info(
        "%d arquivo(s) CSV encontrado(s) em: %s", len(files), directory
    )
    return files

def print_final_summary(results: list[dict]) -> None:
    """Imprime um resumo tabular dos resultados no terminal."""
    print("\n")
    print("━" * 68)
    print("  SUMÁRIO FINAL DO PIPELINE DE ANÁLISE A/B")
    print("━" * 68)

    for r in results:
        status = "✅ SUCESSO" if r["sucesso"] else "❌ FALHOU"
        parceiro = r["parceiro"] or Path(r["arquivo"]).stem
        print(f"\n  {status}  |  {parceiro}  ({r['tempo_s']}s)")

        if r["alertas"]:
            print(f"  {'─'*50}")
            print(f"  ⚠️  {len(r['alertas'])} alerta(s) de qualidade de dados:")
            for a in r["alertas"]:
                print(f"     {a}")

        if r["sucesso"]:
            print(f"  {'─'*50}")
            print(f"  📁 Outputs gerados:")
            for k, v in r["outputs"].items():
                if k == "graficos":
                    print(f"     🖼️  Gráficos: {len(v)} arquivo(s)")
                else:
                    print(f"     📄 {k}: {os.path.basename(v)}")
            if "planilha_url" in r:
                print(f"     📊 Google Sheets: {r['planilha_url']}")
        elif r["erro"]:
            print(f"  ❗ Erro: {r['erro']}")

    print("\n" + "━" * 68)

    n_success = sum(1 for r in results if r["sucesso"])
    print(f"  Total: {n_success}/{len(results)} parceiro(s) processado(s) com sucesso.")
    print("━" * 68 + "\n")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de análise de Testes A/B — Plataforma de Cashback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python src/main.py                               # processa todos os CSVs em datasets/
  python src/main.py --file datasets/parceiro_a.csv  # processa arquivo específico
  python src/main.py --log DEBUG                   # ativa logging detalhado
        """,
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Caminho para um único arquivo CSV a processar (opcional).",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=DATASETS_DIR,
        help=f"Diretório com os datasets CSV (padrão: {DATASETS_DIR}).",
    )
    parser.add_argument(
        "--log",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de logging (padrão: INFO).",
    )
    parser.add_argument(
        "--gemini",
        action="store_true",
        help=(
            "Gera relatórios executivos PDF via Google Gemini após a análise. "
            "Requer GEMINI_API_KEY definida no .env. "
            "Sem essa flag o pipeline roda normalmente sem chamar a API."
        ),
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Com --gemini: salva apenas o Markdown, sem converter para PDF.",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash",
        metavar="MODELO",
        help="Modelo Gemini a usar com --gemini (padrão: gemini-2.5-flash).",
    )
    args = parser.parse_args()

    setup_logging(args.log)
    ensure_dirs()

    logger = logging.getLogger(__name__)
    logger.info("Iniciando pipeline de análise de Testes A/B.")

    if args.file:
        if not os.path.isfile(args.file):
            logger.error("Arquivo não encontrado: %s", args.file)
            sys.exit(1)
        files = [os.path.abspath(args.file)]
    else:
        files = discover_datasets(args.dir)
        if not files:
            logger.error(
                "Nenhum arquivo CSV encontrado em '%s'. "
                "Coloque seus datasets lá ou use --file.",
                args.dir,
            )
            sys.exit(1)

    all_results: list[dict] = []
    all_descriptive: list[pd.DataFrame] = []
    all_hypothesis:  list[pd.DataFrame] = []

    for f in files:
        r = run_pipeline_for_file(f)
        all_results.append(r)
        if r["sucesso"]:
            all_descriptive.append(r.get("_descriptive_df"))
            all_hypothesis.append(r.get("_hypothesis_df"))

    if len([r for r in all_results if r["sucesso"]]) > 1:
        logger.info("Consolidando relatórios de todos os parceiros…")
        consolidate_reports(all_descriptive, all_hypothesis)

    print_final_summary(all_results)

    gemini_results = []
    if args.gemini:
        gemini_results = _run_gemini_reports(all_results, args)

    # --- INTEGRAÇÃO GOOGLE SHEETS & GOOGLE DRIVE ---
    from datetime import datetime
    credentials_path = os.getenv("GOOGLE_CLIENT_SECRET_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_TOKEN_JSON", "token.json")
    if credentials_path and os.path.exists(credentials_path):
        try:
            from src.gsheets_logger import log_test_result, upload_pdf_to_drive
            
            for r in all_results:
                if not r["sucesso"] or "summary" not in r:
                    continue
                
                summary = r["summary"]
                parceiro = r["parceiro"]
                
                pdf_link = ""
                # Verifica se há PDF gerado para esse parceiro no gemini_results
                pdf_path = ""
                if gemini_results:
                    for gr in gemini_results:
                        if gr["parceiro"] == parceiro:
                            pdf_path = gr.get("outputs", {}).get("relatorio_pdf", "")
                            break
                
                if pdf_path and os.getenv("GOOGLE_DRIVE_FOLDER_ID"):
                    pdf_link = upload_pdf_to_drive(pdf_path, credentials_path)
                
                grupo_controle = summary.get("metadata", {}).get("grupo_controle", "Grupo 1")
                vencedora = grupo_controle
                resultado_estatistico = "Nenhuma variante superou o controle com significância."
                maior_lucro_variante = -float('inf')
                
                for comp in summary.get("comparacoes", []):
                    if comp.get("metrica") == "lucro":
                        ttest_p = comp.get("ttest", {}).get("p_value", 1.0)
                        m_var = comp.get("media_variante", 0)
                        m_ctrl = comp.get("media_controle", 0)
                        
                        if ttest_p is not None and ttest_p < 0.05 and m_var > m_ctrl:
                            if m_var > maior_lucro_variante:
                                maior_lucro_variante = m_var
                                vencedora = comp.get("grupo_variante")
                                resultado_estatistico = f"{vencedora} superou {grupo_controle} (p={ttest_p:.4f})"
                
                decisao = f"Manter {grupo_controle}" if vencedora == grupo_controle else f"Escalar {vencedora} para 100% do tráfego"
                
                test_data = {
                    "nome_teste": f"Teste A/B — {parceiro}",
                    "descricao": "Análise automatizada de testes A/B",
                    "periodo_inicio": summary.get("metadata", {}).get("periodo_inicio", "")[:10] if summary.get("metadata", {}).get("periodo_inicio") else "",
                    "periodo_fim": summary.get("metadata", {}).get("periodo_fim", "")[:10] if summary.get("metadata", {}).get("periodo_fim") else "",
                    "grupos": ", ".join(summary.get("metadata", {}).get("grupos", [])),
                    "grupo_controle": grupo_controle,
                    "variante_vencedora": vencedora,
                    "resultado_estatistico": resultado_estatistico,
                    "decisao": decisao,
                    "data_analise": datetime.now().strftime('%d/%m/%Y'),
                    "link_relatorio": pdf_link
                }
                
                sheet_url = log_test_result(test_data, credentials_path)
                logger.info("[%s] Registrado no Google Sheets: %s", parceiro, sheet_url)
        except Exception as e:
            logger.warning("Erro ao registrar no Google Sheets/Drive (ignorado): %s", e)
    else:
        logger.info("GOOGLE_SERVICE_ACCOUNT_JSON não configurado no .env. Pulando envio para Google Sheets.")

def _run_gemini_reports(pipeline_results: list[dict], args) -> list[dict]:
    """
    Executa a geração de relatórios Gemini para todos os parceiros
    que foram processados com sucesso pelo pipeline.

    Chamada apenas quando --gemini está presente.
    """
    logger = logging.getLogger(__name__)

    try:
        from src.gemini_report import process_json_file, load_prompt_template
    except ImportError as e:
        logger.error(
            "❌ Não foi possível importar src.gemini_report: %s\n"
            "   Execute: pip install google-genai", e
        )
        return

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "⚠️  --gemini ativado, mas GEMINI_API_KEY não encontrada.\n"
            "   Crie um arquivo .env na raiz com: GEMINI_API_KEY=sua_chave\n"
            "   Obtenha gratuitamente em: https://aistudio.google.com/app/apikey\n"
            "   Pulando geração de relatórios Gemini."
        )
        return []

    try:
        prompt_template = load_prompt_template()
    except FileNotFoundError as e:
        logger.error("❌ %s", e)
        return []

    successful = [r for r in pipeline_results if r["sucesso"]]
    logger.info("Gerando relatórios Gemini para %d parceiro(s)…", len(successful))

    gemini_results: list[dict] = []
    for i, r in enumerate(successful):
        if i > 0:
            time.sleep(5)  # evita rate limit entre chamadas

        json_path = r["outputs"].get("json_completo")
        if not json_path:
            logger.warning("JSON não encontrado para '%s'. Pulando.", r["parceiro"])
            continue

        gr = process_json_file(
            json_path=json_path,
            model_name=args.gemini_model,
            generate_pdf=not args.no_pdf,
            prompt_template=prompt_template,
        )
        gemini_results.append(gr)

    print("\n" + "━" * 68)
    print("  SUMÁRIO — RELATÓRIOS GEMINI")
    print("━" * 68)
    n_ok = sum(1 for g in gemini_results if g["sucesso"])
    for g in gemini_results:
        status = "✅" if g["sucesso"] else "❌"
        print(f"  {status}  {g['parceiro'] or g['json_path']}")
        if g["sucesso"]:
            for k, v in g["outputs"].items():
                print(f"       📄 {k}: {Path(v).name}")
        else:
            print(f"       Erro: {g['erro']}")
    print(f"\n  Total: {n_ok}/{len(gemini_results)} relatório(s) Gemini gerado(s).")
    print("━" * 68 + "\n")
    return gemini_results

if __name__ == "__main__":
    main()
