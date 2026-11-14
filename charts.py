"""Construcción de gráficos Plotly a partir de columnas seleccionadas."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLOTLY_TEMPLATE = "plotly_dark"


def build_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    aggregation: str = "sum",
    top_n: int = 25,
):
    """Construye un gráfico dinámico. Devuelve una figura Plotly."""
    if df.empty:
        raise ValueError("No hay registros para graficar con los filtros actuales.")

    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    if chart_type == "heatmap":
        if len(numeric_columns) < 2:
            raise ValueError("El mapa de calor necesita al menos dos columnas numéricas.")
        corr = df[numeric_columns].corr(numeric_only=True)
        fig = px.imshow(
            corr,
            text_auto=".2f",
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
            aspect="auto",
            title="Matriz de correlación",
        )
        return _apply_theme(fig)

    if chart_type in {"histogram", "dispersión"}:
        if chart_type == "histogram":
            if not x_column:
                raise ValueError("Selecciona una columna numérica para el histograma.")
            fig = px.histogram(df, x=x_column, nbins=30, title=f"Distribución de {x_column}")
            return _apply_theme(fig)
        if not x_column or not y_column:
            raise ValueError("Selecciona dos columnas numéricas para el gráfico de dispersión.")
        if x_column not in numeric_columns or y_column not in numeric_columns:
            raise ValueError("El gráfico de dispersión requiere columnas numéricas.")
        fig = px.scatter(
            df,
            x=x_column,
            y=y_column,
            hover_data=[col for col in df.columns if col not in {x_column, y_column}][:5],
            title=f"Relación entre {x_column} y {y_column}",
        )
        return _apply_theme(fig)

    if chart_type in {"barras", "líneas", "circular"}:
        if not x_column:
            raise ValueError("Selecciona una columna para el eje X.")
        if x_column not in df.columns:
            raise ValueError("La columna seleccionada no existe.")

        if y_column and y_column in df.columns:
            if aggregation == "count":
                grouped = df.groupby(x_column, dropna=False)[y_column].count().reset_index(name="Valor")
            else:
                if aggregation not in {"sum", "mean", "median", "min", "max"}:
                    raise ValueError("Agregación no válida.")
                grouped = df.groupby(x_column, dropna=False)[y_column].agg(aggregation).reset_index(name="Valor")
            value_label = f"{aggregation} de {y_column}"
        else:
            grouped = df.groupby(x_column, dropna=False).size().reset_index(name="Valor")
            value_label = "Número de registros"

        grouped[x_column] = grouped[x_column].fillna("(Nulo)").astype(str)
        grouped = grouped.sort_values("Valor", ascending=False, kind="stable").head(top_n)

        if chart_type == "barras":
            fig = px.bar(grouped, x=x_column, y="Valor", title=f"{value_label} por {x_column}", text_auto=".3s")
        elif chart_type == "líneas":
            # Ordena por la categoría para evitar saltos arbitrarios en el eje X.
            grouped = grouped.sort_values(x_column, kind="stable")
            fig = px.line(grouped, x=x_column, y="Valor", markers=True, title=f"{value_label} por {x_column}")
        else:
            fig = px.pie(grouped, names=x_column, values="Valor", title=f"Distribución por {x_column}", hole=0.42)
        fig.update_layout(yaxis_title=value_label)
        return _apply_theme(fig)

    raise ValueError(f"Tipo de gráfico no reconocido: {chart_type}")


def _apply_theme(fig):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#dbe4f0"),
        margin=dict(l=18, r=18, t=58, b=24),
        title=dict(x=0.02, xanchor="left", font=dict(size=17)),
        legend_title_text="",
        hoverlabel=dict(bgcolor="#182235", font_color="#f2f5fa"),
    )
    return fig
