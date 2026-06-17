"""
src/visualizations.py
=====================
Gerador de visualizações estatísticas para os Testes A/B.

Gráficos gerados por parceiro:
  1. Gráfico de Linha (Série Temporal) por métrica principal
  2. Heatmap de p-values (visão geral de significância)
"""

import logging
import os

import matplotlib
matplotlib.use("Agg")  # Backend não-interativo (seguro para ambientes sem display)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from config import (
    CHART_DPI,
    CHART_STYLE,
    CHART_PALETTE,
    CHART_FORMAT,
    CHARTS_DIR,
    METRIC_COLUMNS,
    METRIC_LABELS,
    ALPHA,
)

logger = logging.getLogger(__name__)

os.makedirs(CHARTS_DIR, exist_ok=True)

def _save(fig: plt.Figure, filename: str) -> str:
    """Salva a figura em PNG e retorna o caminho completo."""
    path = os.path.join(CHARTS_DIR, filename)
    fig.savefig(path, dpi=CHART_DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info("Gráfico salvo: %s", path)
    return path

def _base_style(n_cols: int = 1) -> tuple[plt.Figure, plt.Axes | np.ndarray]:
    """Cria figura com estilo base dark e grid sutil."""
    plt.style.use(CHART_STYLE)
    fig, axes = plt.subplots(1, n_cols, figsize=(7 * n_cols, 5))
    fig.patch.set_facecolor("#0D1117")
    if n_cols == 1:
        axes.set_facecolor("#161B22")
    else:
        for ax in axes:
            ax.set_facecolor("#161B22")
    return fig, axes

def plot_timeseries(df: pd.DataFrame, parceiro: str) -> list[str]:
    
    paths = []
    if "data" not in df.columns:
        logger.warning("[%s] Coluna 'data' não encontrada. Pulando gráfico de linha.", parceiro)
        return paths

    grupos = sorted(df["grupo"].unique())
    parceiro_slug = parceiro.lower().replace(" ", "_")

    metricas_chave = ["lucro", "vendas_totais", "compradores", "roi_cashback"]

    for metric in metricas_chave:
        if metric not in df.columns:
            continue

        fig, ax = _base_style()
        fig.set_size_inches(10, 5.5)
        ax.set_facecolor("#161B22")

        plotted = False
        for i, grupo in enumerate(grupos):
            gdf = df[df["grupo"] == grupo].sort_values("data")
            if gdf.empty:
                continue
                
            # Agrupa por data caso haja mais de um registro por dia
            gdf_agg = gdf.groupby("data")[metric].sum().reset_index()
            
            color = CHART_PALETTE[i % len(CHART_PALETTE)]
            ax.plot(
                gdf_agg["data"],
                gdf_agg[metric],
                color=color,
                linewidth=2.5,
                marker="o",
                markersize=4,
                label=grupo,
                alpha=0.85
            )
            plotted = True

        if not plotted:
            plt.close(fig)
            continue

        ax.tick_params(colors="#8B949E", labelsize=9)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
        )

        ax.set_title(
            f"{METRIC_LABELS.get(metric, metric)}\nEvolução Temporal — {parceiro}",
            fontsize=13, color="#E6EDF3", pad=12, fontweight="bold",
        )
        ax.set_xlabel("Data", fontsize=11, color="#8B949E")
        ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=10, color="#8B949E")
        
        # Formatação de datas no eixo X
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        fig.autofmt_xdate(rotation=45)

        ax.legend(
            framealpha=0.2, labelcolor="#E6EDF3",
            facecolor="#161B22", edgecolor="#30363D", fontsize=10,
        )
        ax.grid(color="#30363D", linewidth=0.5, linestyle="--")
        ax.spines[:].set_color("#30363D")

        filename = f"{parceiro_slug}_linha_{metric}.{CHART_FORMAT}"
        paths.append(_save(fig, filename))

    return paths



def plot_pvalue_heatmap(hypothesis_df: pd.DataFrame, parceiro: str) -> list[str]:
    """
    Lista com os caminhos dos arquivos PNG gerados.
    """
    paths = []
    if hypothesis_df.empty or "ttest_p" not in hypothesis_df.columns:
        return paths

    parceiro_slug = parceiro.lower().replace(" ", "_")
    df = hypothesis_df[["grupo_variante", "metrica", "ttest_p"]].dropna(
        subset=["ttest_p"]
    )
    if df.empty:
        return paths

    pivot = df.pivot(index="grupo_variante", columns="metrica", values="ttest_p")
    pivot.columns = [METRIC_LABELS.get(c, c) for c in pivot.columns]

    fig, ax = _base_style()
    fig.set_size_inches(max(10, len(pivot.columns) * 1.5), max(4, len(pivot) * 1.2))
    ax.set_facecolor("#161B22")

    cmap = matplotlib.colormaps.get_cmap("RdYlGn").reversed()

    im = ax.imshow(pivot.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    for (i, j), val in np.ndenumerate(pivot.values):
        if np.isnan(val):
            text = "—"
            color = "#8B949E"
        else:
            text = f"{val:.3f}"
            color = "#0D1117" if val < 0.3 else "#E6EDF3"
            if val < ALPHA:
                text += " ✓"
        ax.text(j, i, text, ha="center", va="center", fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=9, color="#E6EDF3")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10, color="#E6EDF3")

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.tick_params(colors="#8B949E", labelsize=8)
    cbar.set_label("p-value", color="#8B949E", fontsize=9)

    ax.set_title(
        f"Heatmap de p-values (Teste T) — {parceiro}\n✓ = significativo (p < {ALPHA})",
        fontsize=12, color="#E6EDF3", pad=12, fontweight="bold",
    )
    ax.spines[:].set_color("#30363D")

    filename = f"{parceiro_slug}_heatmap_pvalues.{CHART_FORMAT}"
    paths.append(_save(fig, filename))

    return paths

def generate_all_charts(
    df: pd.DataFrame,
    hypothesis_df: pd.DataFrame,
    parceiro: str,
) -> list[str]:
  
    all_paths: list[str] = []
    logger.info("[%s] Gerando gráficos…", parceiro)

    all_paths.extend(plot_timeseries(df, parceiro))
    all_paths.extend(plot_pvalue_heatmap(hypothesis_df, parceiro))

    logger.info("[%s] %d gráfico(s) gerado(s).", parceiro, len(all_paths))
    return all_paths
