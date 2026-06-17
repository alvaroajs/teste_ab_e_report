"""
src/analysis.py
Módulo de pré-processamento e limpeza dos dados de Testes A/B.
"""

import re
import logging
import warnings
from typing import Tuple

import numpy as np
import pandas as pd

from config import (
    COLUMN_MAP,
    MONETARY_COLUMNS,
    CONTROL_GROUP,
)

logger = logging.getLogger(__name__)

def _parse_brl_value(value) -> float | None:
    '''
    Converte um valor monetário brasileiro em string para float.
    '''
    if pd.isna(value) or str(value).strip() == "":
        return None

    raw = str(value)

    raw = re.sub(r"[Rr]\$\s*", "", raw).strip()

    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(".", "")

    try:
        return float(raw)
    except ValueError:
        logger.warning("Não foi possível converter o valor monetário: '%s'", value)
        return None

def load_and_clean(filepath: str) -> Tuple[pd.DataFrame, list[str]]:
    '''
    Trata o arquivo A/B.
    '''
    alerts: list[str] = []

    try:
        df_raw = pd.read_csv(filepath, dtype=str, encoding="utf-8")
        logger.info("Arquivo carregado: %s  (%d linhas)", filepath, len(df_raw))
    except UnicodeDecodeError:
        df_raw = pd.read_csv(filepath, dtype=str, encoding="latin-1")
        alerts.append("⚠️  Codificação: arquivo lido com latin-1 (fallback).")
        logger.warning("Codificação latin-1 usada para: %s", filepath)

    missing_cols = [c for c in COLUMN_MAP if c not in df_raw.columns]
    if missing_cols:
        msg = f"🚨 Colunas ausentes no CSV: {missing_cols}"
        alerts.append(msg)
        logger.error(msg)
        raise KeyError(msg)

    df = df_raw.rename(columns=COLUMN_MAP).copy()

    n_before = len(df)
    df.dropna(how="all", inplace=True)
    if len(df) < n_before:
        alerts.append(
            f"⚠️  {n_before - len(df)} linha(s) completamente vazias removidas."
        )

    try:
        df["data"] = pd.to_datetime(df["data"], format="%Y-%m-%d", errors="coerce")
        n_invalid_dates = df["data"].isna().sum()
        if n_invalid_dates:
            alerts.append(f"⚠️  {n_invalid_dates} data(s) inválida(s) → NaT.")
    except Exception as e:
        alerts.append(f"🚨 Erro na conversão de datas: {e}")

    df["compradores"] = pd.to_numeric(
        df["compradores"].str.strip(), errors="coerce"
    )
    n_invalid_buyers = df["compradores"].isna().sum()
    if n_invalid_buyers:
        alerts.append(
            f"⚠️  {n_invalid_buyers} valor(es) inválido(s) em 'compradores' → NaN."
        )

    n_neg = (df["compradores"] < 0).sum()
    if n_neg:
        alerts.append(f"⚠️  {n_neg} valor(es) negativo(s) em 'compradores'.")

    for col in MONETARY_COLUMNS:
        df[col] = df[col].apply(_parse_brl_value)
        n_null = df[col].isna().sum()
        if n_null:
            alerts.append(
                f"⚠️  {n_null} valor(es) nulo(s) ou inválido(s) na coluna '{col}'."
            )

        n_neg = (df[col].dropna() < 0).sum()
        if n_neg:
            alerts.append(f"⚠️  {n_neg} valor(es) negativo(s) em '{col}'.")

    critical_cols = ["compradores"] + MONETARY_COLUMNS
    n_before = len(df)
    df.dropna(subset=critical_cols, inplace=True)
    n_dropped = n_before - len(df)
    if n_dropped:
        alerts.append(
            f"⚠️  {n_dropped} linha(s) removidas por nulos em colunas críticas."
        )

    df["lucro"] = df["comissao"] - df["cashback"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df["roi_cashback"] = np.where(
            df["cashback"] > 0,
            df["vendas_totais"] / df["cashback"],
            np.nan,
        )

    df["ticket_medio"] = np.where(
        df["compradores"] > 0,
        df["vendas_totais"] / df["compradores"],
        np.nan,
    )

    numeric_cols = [
        "compradores", "comissao", "cashback",
        "vendas_totais", "lucro", "roi_cashback", "ticket_medio",
    ]
    for col in numeric_cols:
        actual = str(df[col].dtype)
        if not actual.startswith(("float", "int")):
            alerts.append(
                f"⚠️  Tipo não-numérico em '{col}': obtido {actual}. "
                "Verifique a conversão dos dados."
            )

    if CONTROL_GROUP not in df["grupo"].unique():
        msg = (
            f"🚨 Grupo controle '{CONTROL_GROUP}' não encontrado! "
            f"Grupos disponíveis: {list(df['grupo'].unique())}"
        )
        alerts.append(msg)
        logger.error(msg)

    logger.info(
        "Pré-processamento concluído: %d linhas, %d colunas. Alertas: %d",
        len(df), len(df.columns), len(alerts),
    )

    if alerts:
        logger.warning(
            "Alertas de inconsistências encontrados:\n%s",
            "\n".join(f"  {a}" for a in alerts),
        )

    return df, alerts
