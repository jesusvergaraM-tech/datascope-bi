"""Carga y validación de archivos Excel y CSV."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import pandas as pd

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def validate_extension(filename: str) -> str:
    """Valida la extensión y devuelve el sufijo normalizado."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Formato no compatible. Extensiones permitidas: {allowed}.")
    return suffix


def _make_unique_columns(columns: Iterable[object]) -> list[str]:
    """Convierte encabezados en texto y evita nombres de columna repetidos."""
    result: list[str] = []
    seen: dict[str, int] = {}
    for index, value in enumerate(columns, start=1):
        name = str(value).strip() if value is not None else ""
        if not name or name.lower() == "nan":
            name = f"columna_{index}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        result.append(name if count == 0 else f"{name}_{count + 1}")
    return result


def get_excel_sheets(file_bytes: bytes, filename: str) -> list[str]:
    """Obtiene las hojas disponibles en un archivo XLSX o XLS."""
    suffix = validate_extension(filename)
    if suffix == ".csv":
        return []
    engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
    try:
        with pd.ExcelFile(BytesIO(file_bytes), engine=engine) as workbook:
            return workbook.sheet_names
    except ImportError as exc:
        if suffix == ".xls":
            raise ImportError(
                "Para leer archivos .xls instala xlrd con: pip install xlrd>=2.0.1"
            ) from exc
        raise
    except Exception as exc:
        raise ValueError(f"No fue posible leer las hojas del archivo: {exc}") from exc


def _read_csv(file_bytes: bytes, **kwargs: object) -> pd.DataFrame:
    """Lee CSV probando codificaciones habituales y detectando el separador."""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            frame = pd.read_csv(
                BytesIO(file_bytes),
                sep=None,
                engine="python",
                encoding=encoding,
                **kwargs,
            )
            # Si el detector no identifica el separador y deja todo en una columna,
            # se prueban delimitadores comunes antes de aceptar ese resultado.
            if frame.shape[1] == 1:
                for delimiter in (";", ",", "\t", "|"):
                    candidate = pd.read_csv(
                        BytesIO(file_bytes),
                        sep=delimiter,
                        encoding=encoding,
                        **kwargs,
                    )
                    if candidate.shape[1] > 1:
                        return candidate
            return frame
        except UnicodeDecodeError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
            break
    raise ValueError(f"No fue posible leer el CSV. Revisa el separador y la codificación: {last_error}")


def load_dataset(
    file_bytes: bytes,
    filename: str,
    sheet_name: str | int | None = 0,
) -> pd.DataFrame:
    """Carga un archivo a DataFrame y aplica validaciones básicas.

    XLSX utiliza OpenPyXL. XLS utiliza xlrd (dependencia incluida). CSV intenta
    detectar automáticamente separador y codificación.
    """
    if not file_bytes:
        raise ValueError("El archivo está vacío.")

    suffix = validate_extension(filename)
    try:
        if suffix == ".csv":
            frame = _read_csv(file_bytes)
        else:
            engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
            try:
                frame = pd.read_excel(
                    BytesIO(file_bytes),
                    sheet_name=sheet_name,
                    engine=engine,
                )
            except ImportError as exc:
                if suffix == ".xls":
                    raise ImportError(
                        "No está instalado xlrd, necesario para archivos .xls. "
                        "Ejecuta: pip install xlrd>=2.0.1"
                    ) from exc
                raise
    except Exception as exc:
        if isinstance(exc, (ValueError, ImportError)):
            raise
        raise ValueError(f"No fue posible cargar '{filename}': {exc}") from exc

    if not isinstance(frame, pd.DataFrame):
        raise ValueError("No se pudo seleccionar una única hoja del libro.")
    if frame.empty and len(frame.columns) == 0:
        raise ValueError("El archivo no contiene una tabla con encabezados.")

    frame = frame.copy()
    frame.columns = _make_unique_columns(frame.columns)
    if len(frame.index) == 0:
        raise ValueError("La hoja o archivo no contiene registros debajo de los encabezados.")
    return frame
