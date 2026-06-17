from __future__ import annotations

import logging
import os
import sys
import time
import uuid
import threading
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="A/B Analytics",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)
# ── Garante que a raiz do projeto esteja no sys.path ─────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# ── Controle de Sessão ────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
session_id = st.session_state["session_id"]

import config
config.DATASETS_DIR = os.path.join(config.BASE_DIR, "datasets")
config.REPORTS_DIR  = os.path.join(config.BASE_DIR, "reports")
config.CHARTS_DIR   = os.path.join(config.BASE_DIR, "charts")
config.OUTPUTS_DIR  = os.path.join(config.BASE_DIR, "outputs")
config.LOGS_DIR     = os.path.join(config.BASE_DIR, "logs")

for mod_name in ["src.analysis", "src.statistics", "src.visualizations", "src.reporting", "src.gemini_report"]:
    if mod_name in sys.modules:
        m = sys.modules[mod_name]
        if hasattr(m, "OUTPUTS_DIR"):     m.OUTPUTS_DIR     = os.path.join(config.BASE_DIR, "outputs")
        if hasattr(m, "CHARTS_DIR"):      m.CHARTS_DIR      = os.path.join(config.BASE_DIR, "charts")
        if hasattr(m, "REPORTS_DIR"):     m.REPORTS_DIR     = os.path.join(config.BASE_DIR, "reports")
        if hasattr(m, "REPORTS_OUT_DIR"): m.REPORTS_OUT_DIR = Path(config.BASE_DIR) / "reports" / "gemini"

try:
    from src.analysis       import load_and_clean
    from src.statistics     import compute_descriptive_stats, compute_hypothesis_tests
    from src.visualizations import generate_all_charts
    from src.reporting      import export_csv_descriptive, export_csv_hypothesis, build_full_summary, export_json_full
    from src.gemini_report  import load_and_trim_json, load_prompt_template, build_prompt, call_gemini, markdown_to_pdf, PROMPT_TEMPLATE_PATH
except ImportError as e:
    st.error(f"Erro ao importar módulos do pipeline: {e}")
    st.stop()



# ── Constantes globais ────────────────────────────────────────────────────────
TEMP_DIR    = ROOT_DIR / "temp_datasets"
CHARTS_DIR  = ROOT_DIR / "charts"
OUTPUTS_DIR = ROOT_DIR / "outputs"
REPORTS_DIR = ROOT_DIR / "reports" / "gemini"
GEMINI_MODEL = "gemini-2.5-flash"

STEP_LABELS = {
    1: "Carregando e limpando dados…",
    2: "Calculando estatísticas descritivas…",
    3: "Executando testes de hipótese…",
    4: "Gerando gráficos…",
    5: "Exportando CSV e JSON…",
    6: "Consultando Gemini e gerando PDF…",
}

for d in [TEMP_DIR, CHARTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API KEY ───────────────────────────────────────────────────────────────────
_api_key = ""
try:
    _api_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    pass
if _api_key:
    os.environ["GEMINI_API_KEY"] = _api_key

# ── Injetar fonte via link tag (mais confiável que @import no markdown) ───────
st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

# ── CSS — seletores seguros, sem sobrescrever layout interno do Streamlit ─────
st.markdown("""
<style>
html {
    font-size: 140% !important;
}

/* Aplica Inter apenas em elementos de texto, não no layout */
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown td,
.stMarkdown th, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown span, .stMarkdown strong,
.stTextInput label, .stTextInput input,
.stButton button, .stDownloadButton button,
[data-testid="stSidebarContent"] .stMarkdown p,
[data-testid="stSidebarContent"] .stMarkdown li,
[data-testid="stSidebarContent"] .stMarkdown span,
[data-testid="stSidebarContent"] .stMarkdown strong {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Oculta itens desnecessários ── */
[data-testid="stStatusWidget"] { display: none !important; }
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"][data-collapsed="false"] {
    background-color: #111827 !important;
    border-right: 1px solid #1f2937 !important;
    width: 25% !important;
    min-width: 0vw !important;
    max-width: 25vw !important;
    overflow-y: auto !important;
}
[data-testid="stSidebar"][data-collapsed="true"] {
    width: 0px !important;
    min-width: 0px !important;
    max-width: 0px !important;
    border: none !important;
}
[data-testid="stSidebarContent"] {
    padding: 1rem 0.5rem !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}


/* ── Corpo principal centralizado ── */
.main .block-container {
    max-width: 760px !important;
    padding-top: 6rem !important;
    padding-bottom: 3.5rem !important;
    margin-left: auto !important;
    margin-right: auto !important;
    display: flex !important;
    flex-direction: column !important;
}

/* ── Ajuste de fonte nos expanders da sidebar ── */
[data-testid="stSidebarContent"] [data-testid="stExpanderDetails"] p,
[data-testid="stSidebarContent"] [data-testid="stExpanderDetails"] li {
    font-size: 0.85rem !important;
    line-height: 1.4 !important;
}

/* ── Caixa com Rolagem ── */
.scrollable-box {
    max-height: 180px;
    overflow-y: auto;
    padding: 12px;
    border: 1px solid #30363d;
    border-radius: 6px;
    background-color: #0b0f19;
    margin-top: 10px;
    margin-bottom: 10px;
    font-size: 0.82rem;
}

/* ── Uploader ── */
[data-testid="stFileUploaderDropzone"] {
    border: 1.5px dashed #374151 !important;
    border-radius: 12px !important;
    background-color: #111827 !important;
    transition: border-color 0.2s ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #3b82f6 !important;
}

/* ── Botão primário ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 2px 12px rgba(37, 99, 235, 0.35) !important;
    transition: box-shadow 0.2s, transform 0.15s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 4px 18px rgba(37, 99, 235, 0.55) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:disabled {
    background: #1f2937 !important;
    color: #6b7280 !important;
    box-shadow: none !important;
}

/* ── Log estilo terminal ── */
.log-box {
    background-color: #030712;
    color: #4ade80;
    font-family: 'Fira Code', 'Courier New', Courier, monospace;
    font-size: 0.6rem;
    line-height: 1.35;
    padding: 0.7rem 0.8rem;
    border-radius: 8px;
    border: 1px solid #1f2937;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ── Barra de progresso ── */
.progress-card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
    margin: 0.5rem 0 1rem;
}
.progress-card .step-label {
    font-size: 0.9rem;
    color: #9ca3af;
    margin-top: 0.3rem;
}
.progress-card .step-num {
    font-size: 0.82rem;
    font-weight: 600;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.progress-card .file-label {
    font-size: 0.8rem;
    color: #6b7280;
    margin-bottom: 0.6rem;
}
</style>

<script>
  // impedir que a aba fique piscando
  const targetTitle = "A/B Analytics";
  if (!window.titleObserverInitialized) {
      window.titleObserverInitialized = true;
      document.title = targetTitle;
      
      const observer = new MutationObserver((mutations) => {
          if (document.title !== targetTitle) {
              document.title = targetTitle;
          }
      });
      
      observer.observe(document.head, { childList: true, subtree: true, characterData: true });
      
      try {
          Object.defineProperty(document, 'title', {
              get: function() { return targetTitle; },
              set: function(val) { /* Ignora alterações do Streamlit */ },
              configurable: true
          });
      } catch (e) {
          console.warn("Nao foi possivel congelar document.title via defineProperty:", e);
      }
  }
</script>
""", unsafe_allow_html=True)


# ── Controle da Sidebar e JS (anulação de cache do browser) ───────────────────
if "first_load" not in st.session_state:
    st.session_state["first_load"] = True

if st.session_state["first_load"]:
    st.session_state["sidebar_state"] = "collapsed"
    st.session_state["first_load"] = False
    
    import streamlit.components.v1 as components
    components.html("""
    <script>
        (function() {
            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (attempts > 50) { // Timeout 5s
                    clearInterval(interval);
                    return;
                }
                
                try {
                    const parentDoc = window.parent.document;
                    const expandBtn = parentDoc.querySelector('[data-testid="collapsedControl"]');
                    const collapseBtn = parentDoc.querySelector('[data-testid="stSidebarCollapseButton"]') || 
                                        parentDoc.querySelector('[aria-label="Collapse sidebar"]') || 
                                        parentDoc.querySelector('[aria-label="Close sidebar"]');
                    
                    if (expandBtn) {
                        // Sidebar já colapsada
                        clearInterval(interval);
                    } else if (collapseBtn) {
                        // Sidebar aberta, fecha ela!
                        collapseBtn.click();
                        clearInterval(interval);
                    }
                } catch (e) {
                    console.error('Erro ao fechar sidebar:', e);
                }
            }, 100);
        })();
    </script>
    """, height=0, width=0)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════════════════
class PipelineRunner(threading.Thread):
    def __init__(self, uploaded_files, session_id):
        super().__init__()
        self.uploaded_files = uploaded_files
        self.session_id     = session_id
        self.running   = True
        self.completed = False
        self.cancelled = False
        self.error     = None
        self.current_file = ""
        self.step      = 0
        self.logs      = []
        self.results   = []
        self.temp_files_created = []

    def run(self):
        class _LogHandler(logging.Handler):
            def __init__(self, runner):
                super().__init__(level=logging.INFO)
                self.runner = runner
                self.setFormatter(logging.Formatter(
                    "%(asctime)s  %(name)-20s  %(message)s", datefmt="%H:%M:%S"
                ))
            def emit(self, record):
                try:
                    self.runner.logs.append(self.format(record))
                except Exception:
                    pass

        h = _LogHandler(self)
        root = logging.getLogger()
        for handler in list(root.handlers):
            if handler.__class__.__name__ == "_LogHandler":
                root.removeHandler(handler)
        root.addHandler(h)
        root.setLevel(logging.INFO)

        # Garante que todos os loggers internos do src rodem em nível INFO
        for name in logging.root.manager.loggerDict:
            if name.startswith("src"):
                logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger("src").setLevel(logging.INFO)

        try:
            import shutil
            for d in [TEMP_DIR, CHARTS_DIR, OUTPUTS_DIR, REPORTS_DIR]:
                if d.exists():
                    for item in d.iterdir():
                        try:
                            item.unlink() if item.is_file() else shutil.rmtree(item)
                        except Exception:
                            pass

            for uf in self.uploaded_files:
                if self.cancelled:
                    break
                self.current_file = uf.name
                logging.info(f"--- Iniciando processamento local de {uf.name} ---")

                tmp = TEMP_DIR / uf.name
                tmp.write_bytes(uf.getvalue())
                self.temp_files_created.append(tmp)

                self.step = 1
                logging.info("Etapa 1/6: Carregando e limpando dados do CSV...")
                df_clean, alerts = load_and_clean(str(tmp))
                if self.cancelled: break

                parceiro = (
                    df_clean["parceiro"].mode()[0]
                    if "parceiro" in df_clean.columns and not df_clean["parceiro"].empty
                    else tmp.stem
                )
                logging.info(f"Parceiro identificado: {parceiro}")

                self.step = 2
                logging.info("Etapa 2/6: Calculando métricas estatísticas descritivas por grupo...")
                descriptive_df = compute_descriptive_stats(df_clean, parceiro)
                if self.cancelled: break
                
                self.step = 3
                logging.info("Etapa 3/6: Executando testes de hipótese estatística (T-Test e Mann-Whitney)...")
                hypothesis_df  = compute_hypothesis_tests(df_clean, parceiro)
                if self.cancelled: break
                
                self.step = 4
                logging.info("Etapa 4/6: Gerando visualizações gráficas e temporais localmente...")
                chart_paths    = generate_all_charts(df_clean, hypothesis_df, parceiro)
                if self.cancelled: break

                self.step = 5
                logging.info("Etapa 5/6: Exportando tabelas descritivas e de hipóteses para CSV/JSON...")
                path_desc_csv = export_csv_descriptive(descriptive_df, parceiro)
                path_hyp_csv  = export_csv_hypothesis(hypothesis_df, parceiro)
                summary       = build_full_summary(
                    df_clean=df_clean, descriptive_df=descriptive_df,
                    hypothesis_df=hypothesis_df, parceiro=parceiro,
                    alerts=alerts, chart_paths=chart_paths,
                )
                path_json = export_json_full(summary, parceiro)
                if self.cancelled: break



                self.step = 6
                logging.info("Etapa 6/6: Consultando o Google Gemini e gerando o relatório final PDF...")
                data_trimmed, p_json, cp_json = load_and_trim_json(path_json)
                prompt = build_prompt(
                    data=data_trimmed, parceiro=p_json, chart_paths=cp_json,
                    template=load_prompt_template(PROMPT_TEMPLATE_PATH),
                )
                md_report = call_gemini(prompt, model_name=GEMINI_MODEL, chart_paths=cp_json)
                if self.cancelled: break

                parts = p_json.split(' ')
                if len(parts) == 2 and parts[0].lower() == "parceiro":
                    pdf_filename = f"relatori_parceiro_{parts[1]}.pdf"
                else:
                    pdf_filename = f"relatori_{p_json.lower().replace(' ', '_')}.pdf"
                pdf_path = REPORTS_DIR / pdf_filename
                pdf_ok   = markdown_to_pdf(md_report, pdf_path, p_json)

                # --- GOOGLE SHEETS LOGGING & DRIVE UPLOAD ---
                sheet_url = None
                
                # Suporte a Streamlit Cloud Secrets (onde arquivos físicos não existem)
                inline_token = None
                try:
                    import streamlit as st
                    if "GOOGLE_TOKEN_JSON_INLINE" in st.secrets:
                        inline_token = st.secrets["GOOGLE_TOKEN_JSON_INLINE"]
                except Exception:
                    pass
                
                credentials_path = inline_token or os.getenv("GOOGLE_CLIENT_SECRET_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_TOKEN_JSON", "token.json")
                
                if credentials_path and (credentials_path.startswith("{") or os.path.exists(credentials_path)):
                    try:
                        from src.gsheets_logger import log_test_result, upload_pdf_to_drive
                        from datetime import datetime
                        
                        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
                        try:
                            import streamlit as st
                            if not folder_id and "GOOGLE_DRIVE_FOLDER_ID" in st.secrets:
                                folder_id = st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
                        except Exception:
                            pass
                        
                        pdf_link = ""
                        if pdf_ok and folder_id:
                            # Passa a usar o folder_id na chamada se precisasse, mas o gsheets_logger usa o env
                            # Para forçar o gsheets_logger a enxergar, jogamos pro os.environ
                            os.environ["GOOGLE_DRIVE_FOLDER_ID"] = folder_id
                            pdf_link = upload_pdf_to_drive(str(pdf_path), credentials_path)
                        
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
                        logging.info(f"Registrado no Google Sheets: {sheet_url}")
                    except Exception as e:
                        logging.warning(f"Erro ao registrar no Google Sheets (ignorado): {e}")

                self.results.append({
                    "parceiro":  parceiro,
                    "pdf_ok":    pdf_ok,
                    "pdf_path":  pdf_path,
                    "desc_path": Path(path_desc_csv),
                    "hyp_path":  Path(path_hyp_csv),
                    "alerts":    alerts,
                    "md_report": md_report,
                    "planilha_url": sheet_url,
                })

                if len(self.uploaded_files) > 1 and uf != self.uploaded_files[-1]:
                    for _ in range(50):
                        if self.cancelled: break
                        time.sleep(0.1)

            if not self.cancelled:
                self.completed = True

        except Exception as e:
            self.error = e
        finally:
            self.running = False
            for tmp in self.temp_files_created:
                try: tmp.unlink(missing_ok=True)
                except Exception: pass
            root.removeHandler(h)


def get_file_summary_text(file_path: Path) -> str:
    """Retorna um resumo descritivo sutil do conteúdo do arquivo."""
    name = file_path.name
    if name.endswith(".pdf"):
        return "Relatório de 5 páginas contendo o sumário executivo, desempenho, gráficos temporais e ROI financeiro do teste."
    elif name.endswith(".csv"):
        import pandas as pd
        import config
        try:
            df = pd.read_csv(file_path, sep=config.CSV_SEPARATOR)
            n_rows, n_cols = df.shape
        except Exception:
            try:
                df = pd.read_csv(file_path, sep=",")
                n_rows, n_cols = df.shape
            except Exception:
                n_rows, n_cols = "N/A", "N/A"
        
        dim_text = f" ({n_rows} linhas, {n_cols} colunas)" if n_rows != "N/A" else ""
        if "descritivas" in name:
            return f"Métricas descritivas (média, mediana, soma, desvio padrão) calculadas por grupo{dim_text}."
        elif "hipotese" in name or "hipoteses" in name:
            return f"Testes estatísticos de significância (T-Test, Mann-Whitney U, p-values, Cohen's d){dim_text}."
        else:
            return f"Dados tabulares processados{dim_text}."
    return "Arquivo de suporte gerado no pipeline."



def render_nerd_logs(runner_obj: PipelineRunner | None = None) -> None:
   
    with st.sidebar:
        with st.expander("🤓 Área para nerds"):
            st.markdown("**Log em tempo real**")
            if runner_obj is not None and runner_obj.logs:
                logs_text = "\n".join(runner_obj.logs[-60:])
            else:
                logs_text = "Aguardando início do processamento…"
            st.markdown(f'<div class="log-box">{logs_text}</div>', unsafe_allow_html=True)


@st.fragment(run_every=1.0)
def show_progress_and_logs(runner_obj: PipelineRunner, log_container) -> None:
    """Renderiza o progresso e logs em tempo real usando Streamlit fragments para evitar piscamento."""
    label = STEP_LABELS.get(runner_obj.step, "Preparando…")
    progress_pct = max(runner_obj.step - 1, 0) / 6

    st.markdown(
        f"""
        <div class="progress-card">
            <div class="file-label">Processando: <code>{runner_obj.current_file}</code></div>
            <div class="step-num">Etapa {runner_obj.step} de 6</div>
            <div class="step-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(progress_pct)

    if runner_obj.step == 6:
        st.info("ℹ️ **Nota:** Esta etapa pode demorar até 2min por parceiro. O Gemini 2.5 Flash está realizando uma análise detalhada dos dados e interpretando visualmente os gráficos gerados.", icon="⏳")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.get("confirm_cancel", False):
        st.warning("Deseja cancelar a análise em andamento?")
        c1, c2 = st.columns(2)
        if c1.button("Cancelar agora", type="primary", use_container_width=True, key="cancel_now"):
            runner_obj.cancelled = True
            st.session_state["pipeline_runner"] = None
            st.session_state["confirm_cancel"]  = False
            st.rerun()
        if c2.button("Continuar", use_container_width=True, key="continue_run"):
            st.session_state["confirm_cancel"] = False
            st.rerun()
    else:
        if st.button("Cancelar análise", use_container_width=True, key="cancel_confirm"):
            st.session_state["confirm_cancel"] = True
            st.rerun()

    # Renderiza logs na sidebar em tempo real usando o container passado
    with log_container.container():
        st.divider()
        with st.expander("🤓 Área para nerds", expanded=True):
            st.markdown("**Log em tempo real**")
            if runner_obj.logs:
                logs_text = "\n".join(runner_obj.logs[-60:])
            else:
                logs_text = "Aguardando início do processamento…"
            st.markdown(f'<div class="log-box">{logs_text}</div>', unsafe_allow_html=True)

    # Força o recarregamento completo da tela de resultados/erro assim que o runner parar de rodar
    if not runner_obj.running:
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
runner = st.session_state.get("pipeline_runner", None)

with st.sidebar:

    # Cabeçalho da sidebar
    st.markdown("## 📊 A/B Analytics")
    st.caption("Pipeline estatístico + Google Gemini")
    st.divider()

    # API Key
    api_key_env = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key_env:
        st.markdown("**🔑 API Key do Gemini**")
        user_key = st.text_input(
            "Chave Gemini",
            type="password",
            placeholder="Cole sua chave aqui…",
            label_visibility="collapsed",
        )
        if user_key.strip():
            os.environ["GEMINI_API_KEY"] = user_key.strip()
    else:
        st.success("API Key configurada", icon="✅")

    st.divider()

    # Pipeline — expanders
    st.markdown("**Pipeline**")

    with st.expander("Como funciona"):
        st.markdown("""
**1 · Tratamento local**

Os dados do CSV são carregados, limpos e validados localmente. O pipeline calcula estatísticas descritivas por grupo (médias, medianas, conversões) e executa testes de hipótese (t‑Student e Mann‑Whitney U). Os gráficos são gerados localmente — nenhum dado bruto vai para a nuvem.

**2 · Relatório com Gemini**

Apenas o JSON consolidado das estatísticas é enviado ao modelo `gemini-2.5-flash`. O modelo interpreta significância, calcula uplift e escreve o relatório executivo, exportado como PDF.
        """)

    with st.expander("Etapas do processamento"):
        st.markdown("""
1. Carregamento e limpeza dos dados  
2. Estatísticas descritivas por grupo  
3. Testes de hipótese (T‑test / Mann‑Whitney)  
4. Geração de gráficos  
5. Exportação CSV e JSON  
6. Consulta ao Gemini → PDF  
        """)

    st.divider()

    # Guia de uso
    st.markdown("**Guia de uso**")

    with st.expander("Formato do CSV"):
        st.markdown("""
7 colunas obrigatórias:

| Coluna | Tipo |
|---|---|
| `Data` | `AAAA-MM-DD` |
| `Grupos de usuários` | `Grupo 1` / `Grupo 2` |
| `Parceiro` | Texto |
| `compradores` | Inteiro |
| `comissão` | BRL |
| `cashback` | BRL |
| `vendas totais` | BRL |

Separador: `,` ou `;` · Grupo controle: **Grupo 1** · Um CSV por parceiro.
        """)



    st.divider()


# ══════════════════════════════════════════════════════════════════════════════
# ÁREA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
runner = st.session_state.get("pipeline_runner", None)


if runner is not None and runner.completed:

    st.success("✅ Análise concluída com sucesso.")

    if st.button("⟳  Nova análise", use_container_width=True, key="nova_analise_top"):
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["pipeline_runner"] = None
        st.rerun()

    st.divider()

    for res in runner.results:
        st.subheader(res["parceiro"])

        if res["alerts"]:
            with st.expander(f"⚠ {len(res['alerts'])} alerta(s) de qualidade de dados"):
                for a in res["alerts"]:
                    st.warning(a)

        # Visualização e Download do PDF
        if res["pdf_ok"] and res["pdf_path"].exists():
            st.download_button(
                "⬇  Baixar relatório PDF",
                data=res["pdf_path"].read_bytes(),
                file_name=res["pdf_path"].name,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key=f"pdf_{res['parceiro']}",
            )
            
            # Visualizador PDF embutido na tela (tamanho aumentado em 20% -> 960px)
            import base64
            pdf_bytes = res["pdf_path"].read_bytes()
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="960" style="border: 1px solid #1f2937; border-radius: 8px; margin-bottom: 20px;" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.error("PDF não gerado — WeasyPrint não disponível.")

        c1, c2 = st.columns(2)
        if res["desc_path"].exists():
            c1.download_button(
                "Descritivas (CSV)",
                data=res["desc_path"].read_bytes(),
                file_name=res["desc_path"].name,
                mime="text/csv",
                use_container_width=True,
                key=f"desc_{res['parceiro']}",
            )
        if res["hyp_path"].exists():
            c2.download_button(
                "Hipóteses (CSV)",
                data=res["hyp_path"].read_bytes(),
                file_name=res["hyp_path"].name,
                mime="text/csv",
                use_container_width=True,
                key=f"hyp_{res['parceiro']}",
            )

        # Resumo dos arquivos (tamanhos/linhas/variáveis)
        summary_md = f"""
<div class="scrollable-box">
<strong style="color: #60a5fa; font-size: 0.9rem;">📋 Resumo dos Arquivos Gerados ({res['parceiro']})</strong><br><br>
<ul>
    <li><strong>PDF:</strong> <code>{res['pdf_path'].name}</code> ({res['pdf_path'].stat().st_size / 1024:.1f} KB)<br>
    <span style="color: #9ca3af;">{get_file_summary_text(res['pdf_path'])}</span></li>
    <li style="margin-top: 8px;"><strong>CSV Descritivas:</strong> <code>{res['desc_path'].name}</code> ({res['desc_path'].stat().st_size / 1024:.1f} KB)<br>
    <span style="color: #9ca3af;">{get_file_summary_text(res['desc_path'])}</span></li>
    <li style="margin-top: 8px;"><strong>CSV Hipóteses:</strong> <code>{res['hyp_path'].name}</code> ({res['hyp_path'].stat().st_size / 1024:.1f} KB)<br>
    <span style="color: #9ca3af;">{get_file_summary_text(res['hyp_path'])}</span></li>
</ul>
</div>
        """
        st.markdown(summary_md, unsafe_allow_html=True)
        
        # --- SEÇÃO DO GOOGLE SHEETS ---
        st.markdown("#### Registro de Acompanhamento (Google Sheets)")
        if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            if res.get("planilha_url"):
                st.success("✅ Teste registrado automaticamente na planilha de acompanhamento.")
                st.link_button("Ver planilha de acompanhamento", url=res["planilha_url"], type="secondary", use_container_width=True)
            else:
                st.warning("⚠️ O teste não pôde ser registrado. Verifique os logs para mais detalhes.")
        else:
            st.info("ℹ️ **Dica:** O registro automático no Google Sheets está disponível. Configure a variável `GOOGLE_SERVICE_ACCOUNT_JSON` no seu arquivo `.env` ou nas Secrets do Streamlit.")

        st.divider()

   
    render_nerd_logs(runner)


elif runner is not None and runner.running:

    sidebar_log_placeholder = st.sidebar.empty()
    show_progress_and_logs(runner, sidebar_log_placeholder)

# ── ERRO ──────────────────────────────────────────────────────────────────────
elif runner is not None and runner.error:

    st.error(f"Erro durante a execução: {runner.error}")
    if st.button("⟳  Recomeçar", type="primary", use_container_width=True):
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["pipeline_runner"] = None
        st.rerun()

   
    render_nerd_logs(runner)

# ── IDLE (upload) ─────────────────────────────────────────────────────────────
else:
    # Espaçador flexível superior para centralizar o conteúdo do upload verticalmente
    st.markdown("<div style='flex-grow: 1;'></div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="text-align: center;">
            <h2 style="font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; color: #ffffff;">📊 Análise de Testes A/B</h2>
            <p style="font-size: 1rem; color: #9ca3af; margin-bottom: 1.8rem;">
                Envie os CSVs dos seus parceiros e gere um relatório executivo com IA.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    uploaded_files = st.file_uploader(
        "Arquivos CSV dos parceiros",
        type=["csv"],
        accept_multiple_files=True,
        help="Selecione um ou mais arquivos CSV. Um arquivo por parceiro.",
        label_visibility="collapsed"
    )

    api_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())

    st.markdown("<br>", unsafe_allow_html=True)

    # Centralizar o botão de ação
    c_run = st.columns([1, 2, 1])
    with c_run[1]:
        run = st.button(
            "Rodar análise",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_files and api_ok),
            key="run_btn"
        )

    if not api_ok:
        st.info("Configure a **API Key do Gemini** na barra lateral para habilitar a análise.", icon="🔑")

    if run and uploaded_files and api_ok:
        st.session_state["pipeline_runner"] = PipelineRunner(uploaded_files, session_id)
        st.session_state["confirm_cancel"]  = False
        st.session_state["pipeline_runner"].start()
        st.rerun()

  
    render_nerd_logs(runner)

