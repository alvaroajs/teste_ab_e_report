"""
config.py
=========
Configurações centrais do pipeline de análise de Testes A/B.
Edite este arquivo para personalizar caminhos, parâmetros estatísticos e metadados.
"""

import os

# ─────────────────────────────────────────────
# DIRETÓRIOS DO PROJETO
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASETS_DIR  = os.path.join(BASE_DIR, "datasets")
REPORTS_DIR   = os.path.join(BASE_DIR, "reports")
CHARTS_DIR    = os.path.join(BASE_DIR, "charts")
OUTPUTS_DIR   = os.path.join(BASE_DIR, "outputs")
LOGS_DIR      = os.path.join(BASE_DIR, "logs")

# ─────────────────────────────────────────────
# SCHEMA DOS DADOS DE ENTRADA
# ─────────────────────────────────────────────
# Mapeamento: nome da coluna no CSV → nome interno usado no pipeline
COLUMN_MAP = {
    "Data":               "data",
    "Grupos de usuários": "grupo",
    "Parceiro":           "parceiro",
    "compradores":        "compradores",
    "comissão":           "comissao",
    "cashback":           "cashback",
    "vendas totais":      "vendas_totais",
}

# Colunas monetárias que precisam de parsing (string → float)
MONETARY_COLUMNS = ["comissao", "cashback", "vendas_totais"]



# Todas as métricas que serão analisadas estatisticamente
METRIC_COLUMNS = [
    "compradores",
    "vendas_totais",
    "comissao",
    "cashback",
    "lucro",
    "roi_cashback",
    "ticket_medio",
]

# Rótulo amigável para cada métrica (usado em gráficos e relatórios)
METRIC_LABELS = {
    "compradores":   "Compradores (únicos/dia)",
    "vendas_totais": "Vendas Totais — GMV (R$)",
    "comissao":      "Comissão (R$)",
    "cashback":      "Cashback Distribuído (R$)",
    "lucro":         "Lucro Líquido (R$)",
    "roi_cashback":  "ROI do Cashback (vendas/cashback)",
    "ticket_medio":  "Ticket Médio (R$)",
}

# ─────────────────────────────────────────────
# PARÂMETROS ESTATÍSTICOS
# ─────────────────────────────────────────────
ALPHA             = 0.05          # Nível de significância (5%)
CONFIDENCE_LEVEL  = 0.95          # Intervalo de confiança (95%)
CONTROL_GROUP     = "Grupo 1"     # Grupo de controle (referência)

# Número mínimo de observações para executar testes de hipótese
MIN_OBSERVATIONS  = 5

# ─────────────────────────────────────────────
# CONFIGURAÇÕES DE VISUALIZAÇÃO
# ─────────────────────────────────────────────
CHART_DPI      = 150
CHART_STYLE    = "dark_background"
CHART_PALETTE  = ["#4FC3F7", "#81C784", "#FF8A65", "#CE93D8"]  # Cores por grupo
CHART_FORMAT   = "png"

# ─────────────────────────────────────────────
# CONFIGURAÇÕES DE SAÍDA
# ─────────────────────────────────────────────
CSV_SEPARATOR  = ";"              # Separador dos CSVs de saída
CSV_DECIMAL    = ","              # Separador decimal dos CSVs de saída
JSON_INDENT    = 2                # Indentação do JSON de saída
