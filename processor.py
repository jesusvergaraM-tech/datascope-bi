"""Limpieza, perfilado, filtrado y agrupación de datos."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def get_data_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un perfil de calidad y tipo para cada columna."""
    rows: list[dict[str, Any]] = []
    total = len(df)
    for column in df.columns:
        series = df[column]
        nulls = int(series.isna().sum())
        rows.append(
            {
                "Columna": str(column),
                "Tipo de dato": str(series.dtype),
                "Registros": total,
                "No nulos": int(series.notna().sum()),
                "Nulos": nulls,
                "% nulos": round((nulls / total * 100) if total else 0, 2),
                "Valores únicos": int(series.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def infer_column_types(df: pd.DataFrame, threshold: float = 0.90) -> pd.DataFrame:
    """Intenta convertir texto a número/fecha sin forzar conversiones dudosas."""
    result = df.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        series = result[column]
        non_null = series.dropna().astype(str).str.strip()
        if non_null.empty:
            continue

        # Evita convertir identificadores que suelen tener ceros a la izquierda.
        has_leading_zero_id = non_null.str.match(r"^0\d+$").any()
        numeric = pd.to_numeric(series, errors="coerce")
        numeric_ratio = numeric.notna().sum() / max(series.notna().sum(), 1)
        if numeric_ratio >= threshold and not has_leading_zero_id:
            result[column] = numeric
            continue

        # La conversión de fechas se intenta solo si hay indicios textuales de fecha.
        date_hint = any(token in str(column).lower() for token in ("fecha", "date", "día", "dia", "hora", "time"))
        if date_hint:
            try:
                parsed = pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed")
            except (TypeError, ValueError):
                parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
            date_ratio = parsed.notna().sum() / max(series.notna().sum(), 1)
            if date_ratio >= threshold:
                result[column] = parsed
    return result


def clean_dataframe(
    df: pd.DataFrame,
    *,
    strip_text: bool = True,
    blanks_to_na: bool = True,
    drop_duplicates: bool = False,
    drop_empty_columns: bool = False,
    convert_types: bool = False,
) -> pd.DataFrame:
    """Aplica operaciones de limpieza seleccionadas y devuelve una copia."""
    result = df.copy()

    if strip_text:
        for column in result.select_dtypes(include=["object", "string"]).columns:
            result[column] = result[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

    if blanks_to_na:
        for column in result.select_dtypes(include=["object", "string"]).columns:
            result[column] = result[column].replace(r"^\s*$", np.nan, regex=True)

    if drop_duplicates:
        result = result.drop_duplicates(keep="first")

    if drop_empty_columns:
        non_empty_columns = result.dropna(axis=1, how="all")
        # No deja el conjunto sin estructura si todas las columnas están vacías.
        if len(non_empty_columns.columns) > 0:
            result = non_empty_columns

    if convert_types:
        result = infer_column_types(result)

    return result.reset_index(drop=True)


def apply_filters(df: pd.DataFrame, filters: dict[str, dict[str, Any]] | None = None) -> pd.DataFrame:
    """Aplica filtros opcionales por rangos numéricos, categorías y fechas."""
    if not filters:
        return df.copy()
    result = df.copy()

    for column, bounds in filters.get("numeric", {}).items():
        if column in result.columns and bounds is not None:
            low, high = bounds
            values = pd.to_numeric(result[column], errors="coerce")
            result = result.loc[values.between(low, high) | values.isna()]

    for column, selected in filters.get("categorical", {}).items():
        if column in result.columns and selected is not None:
            if len(selected) == 0:
                result = result.iloc[0:0]
            else:
                result = result.loc[result[column].isin(selected) | result[column].isna()]

    for column, bounds in filters.get("dates", {}).items():
        if column in result.columns and bounds is not None:
            start, end = bounds
            values = pd.to_datetime(result[column], errors="coerce", dayfirst=True)
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            result = result.loc[values.between(start_ts, end_ts) | values.isna()]

    return result.copy()


def aggregate_data(
    df: pd.DataFrame,
    group_columns: list[str],
    value_column: str | None = None,
    aggregation: str = "count",
) -> pd.DataFrame:
    """Agrupa los datos con una función permitida y devuelve una tabla."""
    if not group_columns:
        raise ValueError("Selecciona al menos una columna para agrupar.")
    missing = [col for col in group_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Columnas no encontradas: {', '.join(missing)}")

    allowed = {"count", "sum", "mean", "median", "min", "max"}
    if aggregation not in allowed:
        raise ValueError(f"Agregación no permitida: {aggregation}")

    if value_column is None or aggregation == "count":
        result = df.groupby(group_columns, dropna=False).size().reset_index(name="Registros")
    else:
        if value_column not in df.columns:
            raise ValueError(f"La columna '{value_column}' no existe.")
        result = (
            df.groupby(group_columns, dropna=False)[value_column]
            .agg(aggregation)
            .reset_index(name=f"{aggregation}_{value_column}")
        )
    return result.sort_values(result.columns[-1], ascending=False, kind="stable")
