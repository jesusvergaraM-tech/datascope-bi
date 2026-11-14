"""Indicadores y análisis estadístico descriptivo."""
from __future__ import annotations

import pandas as pd


def dataset_overview(df: pd.DataFrame) -> dict[str, int | float]:
    """Calcula indicadores generales del conjunto de datos."""
    total_cells = int(df.shape[0] * df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    return {
        "registros": int(df.shape[0]),
        "columnas": int(df.shape[1]),
        "celdas_nulas": missing_cells,
        "porcentaje_nulos": round((missing_cells / total_cells * 100) if total_cells else 0, 2),
        "duplicados": int(df.duplicated().sum()),
        "columnas_numericas": int(len(df.select_dtypes(include="number").columns)),
        "columnas_categoricas": int(len(df.select_dtypes(include=["object", "category", "string", "bool"]).columns)),
    }


def summary_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Media, mediana, moda, desviación estándar, máximos y mínimos."""
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame(columns=["Columna", "Conteo", "Media", "Mediana", "Moda", "Desv. estándar", "Mínimo", "Máximo"])

    rows: list[dict[str, object]] = []
    for column in numeric.columns:
        series = numeric[column].dropna()
        modes = series.mode()
        rows.append(
            {
                "Columna": str(column),
                "Conteo": int(series.count()),
                "Media": series.mean(),
                "Mediana": series.median(),
                "Moda": modes.iloc[0] if not modes.empty else None,
                "Desv. estándar": series.std(),
                "Mínimo": series.min(),
                "Máximo": series.max(),
            }
        )
    return pd.DataFrame(rows)


def categorical_frequency(df: pd.DataFrame, column: str, limit: int = 30) -> pd.DataFrame:
    """Frecuencias y porcentaje de una columna categórica."""
    if column not in df.columns:
        raise ValueError(f"La columna '{column}' no existe.")
    counts = df[column].fillna("(Nulo)").astype(str).value_counts(dropna=False).head(limit)
    total = int(df.shape[0])
    result = counts.rename_axis("Categoría").reset_index(name="Frecuencia")
    result["Porcentaje"] = (result["Frecuencia"] / total * 100).round(2) if total else 0
    return result


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz de correlación de Pearson para columnas numéricas."""
    numeric = df.select_dtypes(include="number")
    if numeric.shape[1] < 2:
        return pd.DataFrame()
    return numeric.corr(numeric_only=True)


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen de valores faltantes por columna."""
    total = len(df)
    result = pd.DataFrame(
        {
            "Columna": df.columns.astype(str),
            "Nulos": df.isna().sum().values,
        }
    )
    result["% nulos"] = (result["Nulos"] / total * 100).round(2) if total else 0
    return result.sort_values("Nulos", ascending=False, kind="stable")
