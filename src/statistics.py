"""
src/statistics.py
=================
Motor estatístico do pipeline de Testes A/B.

Calcula, para cada métrica e por grupo:
  A) Estatísticas descritivas e de dispersão (soma, média, mediana, std,
     variância, CV, mín, máx, amplitude, quartis, IQR, skewness, kurtosis)
  B) Testes de hipótese vs. Grupo Controle:
       - Teste T de Student (independente, duas caudas)
       - Teste U de Mann-Whitney (não-paramétrico)
       - Cohen's d (tamanho de efeito)
       - Intervalo de Confiança 95% para a diferença das médias
       - Uplift absoluto e relativo (%)
       - Shapiro-Wilk (normalidade)
"""

import logging
import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import (
    ttest_ind,
    mannwhitneyu,
    shapiro,
)

from config import (
    ALPHA,
    CONFIDENCE_LEVEL,
    CONTROL_GROUP,
    MIN_OBSERVATIONS,
    METRIC_COLUMNS,
    METRIC_LABELS,
)

logger = logging.getLogger(__name__)

def _safe_round(value, decimals: int = 4):
    """Arredonda com segurança; retorna None para NaN/inf."""
    try:
        if value is None or np.isnan(value) or np.isinf(value):
            return None
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None

def _cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float | None:
    """
    Calcula o Cohen's d entre dois grupos independentes.

    d = (μ_b - μ_a) / s_pooled
    onde s_pooled usa os desvios padrões ponderados pelos tamanhos.
    """
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return None
    mean_a, mean_b = np.mean(group_a), np.mean(group_b)
    var_a, var_b = np.var(group_a, ddof=1), np.var(group_b, ddof=1)
    pooled_std = np.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_std == 0:
        return 0.0
    return (mean_b - mean_a) / pooled_std

def _confidence_interval_diff(
    group_a: np.ndarray,
    group_b: np.ndarray,
    confidence: float = 0.95,
) -> tuple[float | None, float | None]:
    """
    Calcula o intervalo de confiança para a diferença entre as médias
    de dois grupos independentes usando a distribuição t de Welch.

    Retorna (lower_bound, upper_bound).
    """
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return None, None
    mean_diff = np.mean(group_b) - np.mean(group_a)
    se = np.sqrt(np.var(group_a, ddof=1) / n_a + np.var(group_b, ddof=1) / n_b)
    if se == 0:
        return mean_diff, mean_diff

    var_a_n = np.var(group_a, ddof=1) / n_a
    var_b_n = np.var(group_b, ddof=1) / n_b
    df_welch = (var_a_n + var_b_n) ** 2 / (
        (var_a_n ** 2 / (n_a - 1)) + (var_b_n ** 2 / (n_b - 1))
    )

    alpha = 1 - confidence
    t_critical = stats.t.ppf(1 - alpha / 2, df=df_welch)
    margin = t_critical * se
    return mean_diff - margin, mean_diff + margin

def compute_descriptive_stats(
    df: pd.DataFrame,
    parceiro: str,
) -> pd.DataFrame:
    
    results = []

    for grupo, gdf in df.groupby("grupo"):
        for metric in METRIC_COLUMNS:
            if metric not in gdf.columns:
                continue

            series = gdf[metric].dropna().values.astype(float)

            if len(series) == 0:
                logger.warning(
                    "[%s] Grupo '%s' — métrica '%s': sem dados.",
                    parceiro, grupo, metric,
                )
                continue

            n = len(series)
            soma = float(np.sum(series))
            media = float(np.mean(series))
            mediana = float(np.median(series))
            std = float(np.std(series, ddof=1)) if n > 1 else 0.0
            variancia = float(np.var(series, ddof=1)) if n > 1 else 0.0
            cv_pct = (std / abs(media) * 100) if media != 0 else None

            minimo = float(np.min(series))
            maximo = float(np.max(series))
            amplitude = maximo - minimo

            q25, q50, q75 = np.percentile(series, [25, 50, 75])
            iqr = q75 - q25

            skewness_val = float(stats.skew(series)) if n >= 3 else None
            kurtosis_val = float(stats.kurtosis(series, fisher=True)) if n >= 4 else None

            results.append({
                "parceiro":    parceiro,
                "grupo":       grupo,
                "metrica":     metric,
                "label":       METRIC_LABELS.get(metric, metric),
                "n_obs":       n,
                "soma":        _safe_round(soma, 2),
                "media":       _safe_round(media, 4),
                "mediana":     _safe_round(mediana, 4),
                "std":         _safe_round(std, 4),
                "variancia":   _safe_round(variancia, 4),
                "cv_pct":      _safe_round(cv_pct, 2),
                "minimo":      _safe_round(minimo, 4),
                "maximo":      _safe_round(maximo, 4),
                "amplitude":   _safe_round(amplitude, 4),
                "q25":         _safe_round(q25, 4),
                "q50":         _safe_round(q50, 4),
                "q75":         _safe_round(q75, 4),
                "iqr":         _safe_round(iqr, 4),
                "skewness":    _safe_round(skewness_val, 4),
                "kurtosis":    _safe_round(kurtosis_val, 4),
            })

    result_df = pd.DataFrame(results)
    logger.info(
        "[%s] Estatísticas descritivas calculadas: %d registros.", parceiro, len(result_df)
    )
    return result_df

def compute_hypothesis_tests(
    df: pd.DataFrame,
    parceiro: str,
) -> pd.DataFrame:
   
    results = []
    grupos = df["grupo"].unique()
    variant_groups = [g for g in grupos if g != CONTROL_GROUP]

    if not any(g == CONTROL_GROUP for g in grupos):
        logger.error(
            "[%s] Grupo controle '%s' não encontrado. Testes impossíveis.",
            parceiro, CONTROL_GROUP,
        )
        return pd.DataFrame()

    control_df = df[df["grupo"] == CONTROL_GROUP]

    for variante in sorted(variant_groups):
        variant_df = df[df["grupo"] == variante]

        for metric in METRIC_COLUMNS:
            if metric not in df.columns:
                continue

            ctrl_vals   = control_df[metric].dropna().values.astype(float)
            var_vals    = variant_df[metric].dropna().values.astype(float)

            n_ctrl  = len(ctrl_vals)
            n_var   = len(var_vals)

            row: dict[str, Any] = {
                "parceiro":           parceiro,
                "grupo_controle":     CONTROL_GROUP,
                "grupo_variante":     variante,
                "metrica":            metric,
                "label":              METRIC_LABELS.get(metric, metric),
                "n_controle":         n_ctrl,
                "n_variante":         n_var,
                "media_controle":     _safe_round(np.mean(ctrl_vals), 4) if n_ctrl > 0 else None,
                "media_variante":     _safe_round(np.mean(var_vals), 4) if n_var > 0 else None,
            }

            for label_grp, vals in [("controle", ctrl_vals), ("variante", var_vals)]:
                sw_stat, sw_p = None, None
                is_normal = None
                try:
                    if len(vals) >= 3:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            sw_stat, sw_p = shapiro(vals)
                            is_normal = bool(sw_p > ALPHA)
                except Exception as e:
                    logger.debug("Shapiro-Wilk falhou (%s/%s): %s", variante, metric, e)

                row[f"shapiro_stat_{label_grp}"]    = _safe_round(sw_stat, 4)
                row[f"shapiro_p_{label_grp}"]        = _safe_round(sw_p, 4)
                row[f"shapiro_normal_{label_grp}"]   = is_normal

            if n_ctrl < MIN_OBSERVATIONS or n_var < MIN_OBSERVATIONS:
                msg = (
                    f"⚠️  [{parceiro}] {variante}/{metric}: amostras insuficientes "
                    f"(ctrl={n_ctrl}, var={n_var}, mín={MIN_OBSERVATIONS})."
                )
                logger.warning(msg)
                row.update({
                    "ttest_stat": None, "ttest_p": None, "ttest_significant": None,
                    "mwu_stat": None, "mwu_p": None, "mwu_significant": None,
                    "cohens_d": None, "cohens_d_magnitude": None,
                    "ci_95_lower": None, "ci_95_upper": None,
                    "uplift_absoluto": None, "uplift_relativo_pct": None,
                    "warning": msg,
                })
                results.append(row)
                continue

            try:
                t_stat, t_p = ttest_ind(ctrl_vals, var_vals, equal_var=False)
                row["ttest_stat"] = _safe_round(t_stat, 4)
                row["ttest_p"]    = _safe_round(t_p, 6)
                row["ttest_significant"] = bool(t_p < ALPHA)
            except Exception as e:
                logger.debug("T-test falhou (%s/%s): %s", variante, metric, e)
                row["ttest_stat"] = None
                row["ttest_p"]    = None
                row["ttest_significant"] = None

            try:
                mwu_stat, mwu_p = mannwhitneyu(
                    ctrl_vals, var_vals, alternative="two-sided"
                )
                row["mwu_stat"] = _safe_round(mwu_stat, 4)
                row["mwu_p"]    = _safe_round(mwu_p, 6)
                row["mwu_significant"] = bool(mwu_p < ALPHA)
            except Exception as e:
                logger.debug("Mann-Whitney falhou (%s/%s): %s", variante, metric, e)
                row["mwu_stat"] = None
                row["mwu_p"]    = None
                row["mwu_significant"] = None

            try:
                d = _cohens_d(ctrl_vals, var_vals)
                row["cohens_d"] = _safe_round(d, 4)
                if d is None:
                    row["cohens_d_magnitude"] = None
                elif abs(d) < 0.2:
                    row["cohens_d_magnitude"] = "negligível"
                elif abs(d) < 0.5:
                    row["cohens_d_magnitude"] = "pequeno"
                elif abs(d) < 0.8:
                    row["cohens_d_magnitude"] = "médio"
                else:
                    row["cohens_d_magnitude"] = "grande"
            except Exception as e:
                logger.debug("Cohen's d falhou (%s/%s): %s", variante, metric, e)
                row["cohens_d"] = None
                row["cohens_d_magnitude"] = None

            try:
                ci_lower, ci_upper = _confidence_interval_diff(
                    ctrl_vals, var_vals, confidence=CONFIDENCE_LEVEL
                )
                row["ci_95_lower"] = _safe_round(ci_lower, 4)
                row["ci_95_upper"] = _safe_round(ci_upper, 4)
            except Exception as e:
                logger.debug("IC falhou (%s/%s): %s", variante, metric, e)
                row["ci_95_lower"] = None
                row["ci_95_upper"] = None

            try:
                mean_ctrl = np.mean(ctrl_vals)
                mean_var  = np.mean(var_vals)
                uplift_abs = mean_var - mean_ctrl
                uplift_rel = (uplift_abs / abs(mean_ctrl) * 100) if mean_ctrl != 0 else None

                row["uplift_absoluto"]    = _safe_round(uplift_abs, 4)
                row["uplift_relativo_pct"] = _safe_round(uplift_rel, 2)
            except Exception as e:
                logger.debug("Uplift falhou (%s/%s): %s", variante, metric, e)
                row["uplift_absoluto"]    = None
                row["uplift_relativo_pct"] = None

            row["warning"] = None
            results.append(row)

    result_df = pd.DataFrame(results)
    logger.info(
        "[%s] Testes de hipótese calculados: %d comparações.", parceiro, len(result_df)
    )
    return result_df
