import json
import logging
import os
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from config import (
    CSV_SEPARATOR,
    CSV_DECIMAL,
    JSON_INDENT,
    OUTPUTS_DIR,
    REPORTS_DIR,
    METRIC_LABELS,
    ALPHA,
    CONFIDENCE_LEVEL,
    CONTROL_GROUP,
)

logger = logging.getLogger(__name__)

os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

def _clean_for_json(obj: Any) -> Any:
    """
    Serializa recursivamente um objeto Python para tipos compatíveis com JSON.
    Trata: numpy scalars, NaN, Inf, datetime, ndarray, DataFrame.
    """
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_for_json(i) for i in obj]
    if isinstance(obj, pd.DataFrame):
        return _clean_for_json(obj.to_dict(orient="records"))
    if isinstance(obj, pd.Series):
        return _clean_for_json(obj.to_dict())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return _clean_for_json(obj.tolist())
    if isinstance(obj, float):
        return None if (np.isnan(obj) or np.isinf(obj)) else obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj

def _parceiro_slug(parceiro: str) -> str:
    """Converte 'Parceiro A' → 'parceiro_a'."""
    return parceiro.lower().replace(" ", "_")

def export_csv_descriptive(
    descriptive_df: pd.DataFrame,
    parceiro: str,
) -> str:
    """
    Exporta as estatísticas descritivas para CSV.

    Arquivo: outputs/[parceiro]_estatisticas_descritivas.csv

    Parâmetros
    ----------
    descriptive_df : DataFrame retornado por compute_descriptive_stats().
    parceiro : Nome do parceiro.

    Retorna
    -------
    Caminho do arquivo gerado.
    """
    filename = f"{_parceiro_slug(parceiro)}_estatisticas_descritivas.csv"
    path = os.path.join(OUTPUTS_DIR, filename)

    descriptive_df.to_csv(
        path,
        sep=CSV_SEPARATOR,
        decimal=CSV_DECIMAL,
        index=False,
        encoding="utf-8-sig",  # BOM para compatibilidade com Excel
    )
    logger.info("CSV descritivo exportado: %s", path)
    return path

def export_csv_hypothesis(
    hypothesis_df: pd.DataFrame,
    parceiro: str,
) -> str:

    filename = f"{_parceiro_slug(parceiro)}_testes_hipotese.csv"
    path = os.path.join(OUTPUTS_DIR, filename)

    hypothesis_df.to_csv(
        path,
        sep=CSV_SEPARATOR,
        decimal=CSV_DECIMAL,
        index=False,
        encoding="utf-8-sig",
    )
    logger.info("CSV de hipóteses exportado: %s", path)
    return path

def build_full_summary(
    df_clean: pd.DataFrame,
    descriptive_df: pd.DataFrame,
    hypothesis_df: pd.DataFrame,
    parceiro: str,
    alerts: list[str],
    chart_paths: list[str],
) -> dict:
    """
    Constrói o dicionário aninhado que será exportado como JSON completo.

    Estrutura do JSON:
    {
      "metadata": { ... informações gerais do teste ... },
      "data_quality": { ... alertas de inconsistência ... },
      "grupos": {
        "Grupo 1": {
          "n_obs": ...,
          "periodo": { ... },
          "metricas": {
            "compradores": { "descritiva": {...}, "serie_temporal": [...] },
            ...
          }
        },
        "Grupo 2": { ... }
      },
      "comparacoes": [
        {
          "grupo_variante": "Grupo 2",
          "metrica": "compradores",
          "ttest": {...},
          "mann_whitney": {...},
          "cohens_d": {...},
          "intervalo_confianca_95": {...},
          "uplift": {...},
          "normalidade": {...}
        },
        ...
      ],
      "charts": [ ... caminhos dos gráficos ... ]
    }

    Parâmetros
    ----------
    df_clean      : DataFrame limpo e processado.
    descriptive_df: Resultado de compute_descriptive_stats().
    hypothesis_df : Resultado de compute_hypothesis_tests().
    parceiro      : Nome do parceiro.
    alerts        : Lista de alertas do pré-processamento.
    chart_paths   : Lista de caminhos dos PNGs gerados.

    Retorna
    -------
    Dicionário Python pronto para serialização JSON.
    """
    grupos = sorted(df_clean["grupo"].unique())
    metrics = list(descriptive_df["metrica"].unique()) if not descriptive_df.empty else []

    metadata = {
        "parceiro": parceiro,
        "gerado_em": datetime.now().isoformat(),
        "periodo_inicio": df_clean["data"].min().isoformat() if "data" in df_clean else None,
        "periodo_fim":    df_clean["data"].max().isoformat() if "data" in df_clean else None,
        "total_observacoes": len(df_clean),
        "grupos": grupos,
        "n_grupos": len(grupos),
        "metricas_analisadas": metrics,
        "n_metricas": len(metrics),
        "grupo_controle": CONTROL_GROUP,
        "alpha": ALPHA,
        "nivel_confianca": CONFIDENCE_LEVEL,
        "labels_metricas": METRIC_LABELS,
    }

    data_quality = {
        "alertas_encontrados": len(alerts),
        "lista_alertas": alerts,
        "dados_por_grupo": {
            g: int((df_clean["grupo"] == g).sum()) for g in grupos
        },
    }

    grupos_dict = {}
    for grupo in grupos:
        gdf = df_clean[df_clean["grupo"] == grupo].sort_values("data")
        g_desc_df = descriptive_df[descriptive_df["grupo"] == grupo]

        metricas_dict = {}
        for metric in metrics:
            m_desc = g_desc_df[g_desc_df["metrica"] == metric]
            desc_dict = (
                m_desc.drop(columns=["parceiro", "grupo", "metrica", "label"], errors="ignore")
                .iloc[0].to_dict()
                if not m_desc.empty else {}
            )

            if "data" in gdf.columns and metric in gdf.columns:
                ts = (
                    gdf[["data", metric]]
                    .dropna()
                    .assign(data=lambda x: x["data"].dt.date.astype(str))
                    .rename(columns={metric: "valor"})
                    .to_dict(orient="records")
                )
            else:
                ts = []

            metricas_dict[metric] = {
                "label":          METRIC_LABELS.get(metric, metric),
                "descritiva":     desc_dict,
                "serie_temporal": ts,
            }

        grupos_dict[grupo] = {
            "n_obs":   int(len(gdf)),
            "periodo": {
                "inicio": str(gdf["data"].min().date()) if "data" in gdf.columns else None,
                "fim":    str(gdf["data"].max().date()) if "data" in gdf.columns else None,
                "n_dias": int(gdf["data"].nunique()) if "data" in gdf.columns else None,
            },
            "metricas": metricas_dict,
        }

    comparacoes = []
    if not hypothesis_df.empty:
        for _, row in hypothesis_df.iterrows():
            comp = {
                "grupo_controle":  row.get("grupo_controle"),
                "grupo_variante":  row.get("grupo_variante"),
                "metrica":         row.get("metrica"),
                "label":           row.get("label"),
                "n_controle":      row.get("n_controle"),
                "n_variante":      row.get("n_variante"),
                "media_controle":  row.get("media_controle"),
                "media_variante":  row.get("media_variante"),
                "ttest": {
                    "estatistica": row.get("ttest_stat"),
                    "p_value":     row.get("ttest_p"),
                    "significativo": row.get("ttest_significant"),
                },
                "mann_whitney": {
                    "estatistica": row.get("mwu_stat"),
                    "p_value":     row.get("mwu_p"),
                    "significativo": row.get("mwu_significant"),
                },
                "cohens_d": {
                    "valor":      row.get("cohens_d"),
                    "magnitude":  row.get("cohens_d_magnitude"),
                },
                "intervalo_confianca_95": {
                    "lower": row.get("ci_95_lower"),
                    "upper": row.get("ci_95_upper"),
                },
                "uplift": {
                    "absoluto":      row.get("uplift_absoluto"),
                    "relativo_pct":  row.get("uplift_relativo_pct"),
                },
                "normalidade": {
                    "controle": {
                        "shapiro_stat":    row.get("shapiro_stat_controle"),
                        "p_value":         row.get("shapiro_p_controle"),
                        "distribuicao_normal": row.get("shapiro_normal_controle"),
                    },
                    "variante": {
                        "shapiro_stat":    row.get("shapiro_stat_variante"),
                        "p_value":         row.get("shapiro_p_variante"),
                        "distribuicao_normal": row.get("shapiro_normal_variante"),
                    },
                },
                "aviso": row.get("warning"),
            }
            comparacoes.append(comp)

    return {
        "metadata":     metadata,
        "data_quality": data_quality,
        "grupos":       grupos_dict,
        "comparacoes":  comparacoes,
        "charts":       chart_paths,
    }

def export_json_full(summary_dict: dict, parceiro: str) -> str:
  
    filename = f"{_parceiro_slug(parceiro)}_resumo_completo.json"
    path = os.path.join(OUTPUTS_DIR, filename)

    clean_dict = _clean_for_json(summary_dict)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_dict, f, ensure_ascii=False, indent=JSON_INDENT)

    logger.info("JSON completo exportado: %s", path)
    return path
