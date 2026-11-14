"""Exportación de resultados a Excel con formato profesional."""
from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .analytics import correlation_matrix, summary_statistics
from .processor import get_data_profile


def _excel_safe(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepara fechas con zona horaria para que Excel pueda almacenarlas."""
    safe = frame.copy()
    for column in safe.columns:
        if isinstance(safe[column].dtype, pd.DatetimeTZDtype):
            safe[column] = safe[column].dt.tz_localize(None)
    return safe


def _all_frequencies(df: pd.DataFrame, limit: int = 100) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for column in df.columns:
        if not pd.api.types.is_numeric_dtype(df[column]) and not pd.api.types.is_datetime64_any_dtype(df[column]):
            counts = df[column].fillna("(Nulo)").astype(str).value_counts().head(limit)
            if not counts.empty:
                part = counts.rename_axis("Valor").reset_index(name="Frecuencia")
                part.insert(0, "Columna", str(column))
                parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["Columna", "Valor", "Frecuencia"])


def _write_sheet(writer: pd.ExcelWriter, name: str, frame: pd.DataFrame) -> None:
    _excel_safe(frame).to_excel(writer, sheet_name=name, index=False)


def _format_workbook(workbook) -> None:
    header_fill = PatternFill("solid", fgColor="14243A")
    header_font = Font(name="Aptos", bold=True, color="FFFFFF", size=10)
    body_font = Font(name="Aptos", color="243247", size=10)
    thin_gray = Side(style="hair", color="D8E0EA")

    for ws in workbook.worksheets:
        ws.freeze_panes = "A2"
        ws.sheet_view.showGridLines = False
        ws.auto_filter.ref = ws.dimensions if ws.max_row > 1 else None
        ws.row_dimensions[1].height = 25

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(bottom=Side(style="medium", color="28B8A8"))

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = body_font
                cell.alignment = Alignment(vertical="center")
                cell.border = Border(bottom=thin_gray)
                if isinstance(cell.value, float):
                    cell.number_format = "#,##0.00;[Red]-#,##0.00"

        for column_cells in ws.columns:
            letter = get_column_letter(column_cells[0].column)
            max_length = max((len(str(cell.value)) if cell.value is not None else 0) for cell in column_cells[:200])
            ws.column_dimensions[letter].width = min(max(max_length + 2, 12), 34)

        # Resalta visualmente el porcentaje de nulos si la hoja de calidad lo contiene.
        if ws.title == "Calidad" and ws.max_row > 1:
            headers = {cell.value: cell.column for cell in ws[1]}
            percent_col = headers.get("% nulos")
            if percent_col:
                letter = get_column_letter(percent_col)
                ws.conditional_formatting.add(
                    f"{letter}2:{letter}{ws.max_row}",
                    DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="25A99A", showValue=True),
                )


def export_to_excel(original_df: pd.DataFrame, filtered_df: pd.DataFrame | None = None) -> bytes:
    """Genera un libro con datos, estadísticas, frecuencias y calidad."""
    filtered = filtered_df if filtered_df is not None else original_df
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _write_sheet(writer, "Datos_originales", original_df)
        _write_sheet(writer, "Datos_filtrados", filtered)
        _write_sheet(writer, "Resumen", summary_statistics(filtered))
        _write_sheet(writer, "Frecuencias", _all_frequencies(filtered))
        _write_sheet(writer, "Calidad", get_data_profile(filtered))
        corr = correlation_matrix(filtered)
        _write_sheet(writer, "Correlaciones", corr.reset_index(names="Variable") if not corr.empty else pd.DataFrame({"Mensaje": ["Se requieren al menos dos columnas numéricas."]}))
        _format_workbook(writer.book)

    buffer.seek(0)
    return buffer.getvalue()
