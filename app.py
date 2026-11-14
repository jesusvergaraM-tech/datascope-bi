"""Aplicación web BI genérica construida con Streamlit."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.analytics import (
    categorical_frequency,
    correlation_matrix,
    dataset_overview,
    missing_summary,
    summary_statistics,
)
from modules.charts import build_chart
from modules.exporter import export_to_excel
from modules.loader import get_excel_sheets, load_dataset
from modules.processor import (
    aggregate_data,
    apply_filters,
    clean_dataframe,
    get_data_profile,
)


BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="DataScope BI | Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css() -> None:
    css_path = BASE_DIR / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_sheets(file_bytes: bytes, filename: str) -> list[str]:
    return get_excel_sheets(file_bytes, filename)


@st.cache_data(show_spinner="Leyendo archivo y preparando los datos…", ttl=3600)
def cached_load(file_bytes: bytes, filename: str, sheet_name: str | None) -> pd.DataFrame:
    return load_dataset(file_bytes, filename, sheet_name=sheet_name or 0)


def page_header(title: str, description: str) -> None:
    st.markdown('<div class="bi-eyebrow">DATASCOPE BI · ANALÍTICA DE DATOS</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="bi-subtitle">{description}</div>', unsafe_allow_html=True)
    st.write("")


def show_empty_state() -> None:
    st.markdown('<div class="bi-eyebrow">DATASCOPE BI · ESPACIO DE TRABAJO</div>', unsafe_allow_html=True)
    st.title("Convierte tus datos en decisiones")
    st.markdown(
        "<div class='bi-subtitle'>Importa un archivo Excel o CSV para comenzar a explorar indicadores, "
        "calidad de datos, estadísticas y visualizaciones interactivas.</div>",
        unsafe_allow_html=True,
    )
    st.write("")
    left, right = st.columns([1.25, 1])
    with left:
        st.markdown(
            """
            <div class="bi-section">
              <h3>Un espacio de análisis, no una plantilla de resultados</h3>
              <p class="bi-muted">Los indicadores y gráficos se calculan únicamente con el archivo que cargues. "
              "No se insertan registros de demostración en el panel.</p>
              <p>📥 Importa datos · 🧹 Revisa su calidad · 📈 Analiza patrones · 📤 Exporta resultados</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="bi-section">
              <h3>Formatos compatibles</h3>
              <p><b>Excel moderno</b><br><span class="bi-muted">.xlsx · Motor OpenPyXL</span></p>
              <p><b>Excel 97–2003</b><br><span class="bi-muted">.xls · Motor xlrd</span></p>
              <p><b>Texto delimitado</b><br><span class="bi-muted">.csv · Detección de separador y codificación</span></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.info("Usa el cargador de archivos del menú lateral. También puedes probar con ejemplo_datos.csv, incluido en el proyecto.")


def build_sidebar_filters(df: pd.DataFrame, fingerprint: str) -> dict:
    """Construye filtros globales; todos los módulos reciben el mismo DataFrame filtrado."""
    filters: dict[str, dict] = {"numeric": {}, "categorical": {}, "dates": {}}
    st.sidebar.divider()
    st.sidebar.markdown("**Filtros del análisis**")
    st.sidebar.caption("Los filtros se aplican al panel, las estadísticas y los gráficos.")

    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    for column in numeric_columns:
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if values.empty:
            continue
        low, high = float(values.min()), float(values.max())
        if low == high:
            continue
        key = f"num_{fingerprint}_{column}"
        with st.sidebar.expander(f"Rango · {column}", expanded=False):
            selected_range = st.slider(
                f"Selecciona el rango de {column}",
                min_value=low,
                max_value=high,
                value=(low, high),
                key=key,
                label_visibility="collapsed",
            )
            if selected_range != (low, high):
                filters["numeric"][column] = selected_range

    date_columns: list[str] = []
    for column in df.columns:
        series = df[column]
        name_hint = any(token in str(column).lower() for token in ("fecha", "date", "hora", "time"))
        if pd.api.types.is_datetime64_any_dtype(series) or (
            name_hint and pd.api.types.is_object_dtype(series)
            and pd.to_datetime(series, errors="coerce", dayfirst=True).notna().mean() >= 0.75
        ):
            date_columns.append(column)

    for column in date_columns:
        dates = pd.to_datetime(df[column], errors="coerce", dayfirst=True).dropna()
        if dates.empty:
            continue
        min_date, max_date = dates.min().date(), dates.max().date()
        if min_date == max_date:
            continue
        key = f"date_{fingerprint}_{column}"
        with st.sidebar.expander(f"Fechas · {column}", expanded=False):
            selected_dates = st.date_input(
                f"Periodo de {column}",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=key,
                label_visibility="collapsed",
            )
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                if selected_dates != (min_date, max_date):
                    filters["dates"][column] = selected_dates

    categorical_columns = df.select_dtypes(include=["object", "category", "string", "bool"]).columns.tolist()
    for column in categorical_columns:
        values = df[column].dropna().unique().tolist()
        if not values or len(values) > 80:
            continue
        key = f"cat_{fingerprint}_{column}"
        with st.sidebar.expander(f"Categorías · {column}", expanded=False):
            selected_values = st.multiselect(
                f"Valores de {column}",
                options=values,
                default=values,
                key=key,
                label_visibility="collapsed",
            )
            if len(selected_values) != len(values):
                filters["categorical"][column] = selected_values

    return filters


def render_overview(df: pd.DataFrame) -> None:
    page_header("Panel principal", "Vista general de la estructura y la calidad del conjunto de datos actual.")
    metrics = dataset_overview(df)
    columns = st.columns(4)
    columns[0].metric("Registros", f"{metrics['registros']:,}")
    columns[1].metric("Columnas", f"{metrics['columnas']:,}")
    columns[2].metric("Celdas nulas", f"{metrics['celdas_nulas']:,}", f"{metrics['porcentaje_nulos']}% del total")
    columns[3].metric("Filas duplicadas", f"{metrics['duplicados']:,}")

    st.write("")
    left, right = st.columns([1.05, 1])
    with left:
        st.subheader("Valores faltantes por columna")
        missing = missing_summary(df)
        missing = missing[missing["Nulos"] > 0].head(15)
        if missing.empty:
            st.success("No se encontraron valores nulos en los datos filtrados.")
        else:
            fig = px.bar(
                missing.sort_values("Nulos"),
                x="Nulos",
                y="Columna",
                orientation="h",
                text="Nulos",
                title="Columnas con mayor cantidad de nulos",
            )
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=12, t=48, b=8))
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Composición de tipos de datos")
        profile = get_data_profile(df)
        type_counts = profile["Tipo de dato"].value_counts().rename_axis("Tipo").reset_index(name="Columnas")
        fig = px.pie(type_counts, names="Tipo", values="Columnas", hole=.48, title="Columnas por tipo")
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=12, t=48, b=8))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Vista previa")
    st.dataframe(df.head(100), use_container_width=True, hide_index=True)
    with st.expander("Perfil detallado de columnas"):
        st.dataframe(profile, use_container_width=True, hide_index=True)


def render_exploration(df: pd.DataFrame) -> None:
    page_header("Explorar datos", "Inspecciona registros, revisa la estructura y construye agrupaciones sin modificar el archivo original.")
    st.subheader("Tabla de datos")
    st.caption(f"Mostrando {min(len(df), 500):,} de {len(df):,} registros filtrados.")
    st.dataframe(df.head(500), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Agrupación dinámica")
    cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    c1, c2, c3 = st.columns(3)
    with c1:
        group_by = st.multiselect("Agrupar por", options=cols, default=cols[:1] if cols else [], max_selections=3)
    with c2:
        value_col = st.selectbox("Columna de valores (opcional)", options=["(Conteo de filas)"] + numeric_cols)
    with c3:
        aggregation = st.selectbox("Operación", options=["count", "sum", "mean", "median", "min", "max"], format_func=lambda x: {"count": "Conteo", "sum": "Suma", "mean": "Promedio", "median": "Mediana", "min": "Mínimo", "max": "Máximo"}[x])

    if group_by:
        try:
            aggregated = aggregate_data(
                df,
                group_by,
                None if value_col == "(Conteo de filas)" else value_col,
                aggregation,
            )
            st.dataframe(aggregated, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.warning(f"No se pudo crear la agrupación: {exc}")
    else:
        st.info("Selecciona una o más columnas para construir la agrupación.")


def render_quality(df: pd.DataFrame) -> None:
    page_header("Calidad y limpieza", "Detecta problemas comunes y aplica una limpieza controlada sobre una copia de los datos.")
    metrics = dataset_overview(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Valores nulos", f"{metrics['celdas_nulas']:,}")
    c2.metric("Filas duplicadas", f"{metrics['duplicados']:,}")
    c3.metric("Columnas", f"{metrics['columnas']:,}")

    st.subheader("Diagnóstico por columna")
    st.dataframe(get_data_profile(df), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Opciones de limpieza")
    st.caption("La limpieza se aplica al conjunto de trabajo. El archivo original permanece disponible para comparar y exportar.")
    c1, c2 = st.columns(2)
    with c1:
        strip_text = st.checkbox("Quitar espacios al inicio y al final del texto", value=True)
        blanks_to_na = st.checkbox("Convertir textos vacíos en valores nulos", value=True)
        drop_duplicates = st.checkbox("Eliminar filas duplicadas", value=True)
    with c2:
        drop_empty_columns = st.checkbox("Eliminar columnas completamente vacías", value=False)
        convert_types = st.checkbox("Intentar detectar números y fechas en columnas de texto", value=False)

    action1, action2 = st.columns([1, 1])
    with action1:
        apply_clicked = st.button("Aplicar limpieza", type="primary", use_container_width=True)
    with action2:
        reset_clicked = st.button("Restablecer datos cargados", use_container_width=True)

    if reset_clicked:
        st.session_state["working_df"] = st.session_state["original_df"].copy()
        st.success("Se restauró la versión cargada del archivo.")
        st.rerun()

    if apply_clicked:
        cleaned = clean_dataframe(
            df,
            strip_text=strip_text,
            blanks_to_na=blanks_to_na,
            drop_duplicates=drop_duplicates,
            drop_empty_columns=drop_empty_columns,
            convert_types=convert_types,
        )
        st.session_state["working_df"] = cleaned
        removed = len(df) - len(cleaned)
        st.success(f"Limpieza aplicada. Registros actuales: {len(cleaned):,}. Filas retiradas: {removed:,}.")
        st.rerun()

    st.info("Los cambios de limpieza no se guardan automáticamente en el archivo de origen. Descarga el resultado desde el módulo Exportar.")


def render_statistics(df: pd.DataFrame) -> None:
    page_header("Análisis estadístico", "Estadística descriptiva, frecuencias y correlaciones calculadas sobre los datos filtrados.")
    stats = summary_statistics(df)
    if stats.empty:
        st.info("No se detectaron columnas numéricas. Puedes revisar la conversión de tipos en Calidad y limpieza.")
    else:
        st.subheader("Estadísticas descriptivas")
        st.dataframe(stats, use_container_width=True, hide_index=True)

    categorical = df.select_dtypes(include=["object", "category", "string", "bool"]).columns.tolist()
    if categorical:
        st.divider()
        st.subheader("Distribución de frecuencias")
        selected_col = st.selectbox("Selecciona una variable categórica", categorical)
        freq = categorical_frequency(df, selected_col, limit=50)
        col1, col2 = st.columns([1, 1.1])
        with col1:
            st.dataframe(freq, use_container_width=True, hide_index=True)
        with col2:
            fig = px.bar(freq.sort_values("Frecuencia"), x="Frecuencia", y="Categoría", orientation="h", title=f"Frecuencia de {selected_col}")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=12, t=48, b=8))
            st.plotly_chart(fig, use_container_width=True)

    corr = correlation_matrix(df)
    if not corr.empty:
        st.divider()
        st.subheader("Correlaciones")
        st.caption("Correlación de Pearson entre variables numéricas. Una relación estadística no implica causalidad.")
        corr_fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="Matriz de correlación", aspect="auto")
        corr_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=8, r=12, t=48, b=8))
        st.plotly_chart(corr_fig, use_container_width=True)


def render_visualizations(df: pd.DataFrame) -> None:
    page_header("Visualizaciones", "Crea gráficos interactivos. Los datos y las agregaciones responden a los filtros laterales.")
    chart_types = ["barras", "líneas", "circular", "histogram", "dispersión", "heatmap"]
    chart_labels = {
        "barras": "Gráfico de barras",
        "líneas": "Gráfico de líneas",
        "circular": "Gráfico circular",
        "histogram": "Histograma",
        "dispersión": "Dispersión",
        "heatmap": "Mapa de calor de correlaciones",
    }
    c1, c2, c3 = st.columns(3)
    with c1:
        chart_type = st.selectbox("Tipo de gráfico", chart_types, format_func=lambda value: chart_labels[value])
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    with c2:
        if chart_type in {"histogram", "dispersión"}:
            x_options = numeric_cols
        else:
            x_options = df.columns.tolist()
        x_column = st.selectbox("Eje X / categoría", options=x_options, disabled=chart_type == "heatmap") if x_options else None
    with c3:
        y_options = numeric_cols
        if chart_type == "dispersión" and y_options:
            default_y_index = 1 if len(y_options) > 1 else 0
            y_column = st.selectbox("Eje Y / valor", options=y_options, index=default_y_index)
        else:
            y_column = st.selectbox("Eje Y / valor (opcional)", options=["(Contar registros)"] + y_options, disabled=chart_type in {"histogram", "heatmap"})

    c4, c5 = st.columns(2)
    with c4:
        aggregation = st.selectbox("Agregación", ["sum", "mean", "median", "min", "max", "count"], format_func=lambda value: {"sum": "Suma", "mean": "Promedio", "median": "Mediana", "min": "Mínimo", "max": "Máximo", "count": "Conteo"}[value], disabled=chart_type in {"histogram", "dispersión", "heatmap"} or y_column == "(Contar registros)")
    with c5:
        top_n = st.slider("Máximo de categorías", min_value=5, max_value=50, value=20, step=5, disabled=chart_type in {"histogram", "dispersión", "heatmap"})

    if chart_type == "heatmap":
        effective_x = effective_y = None
    else:
        effective_x = x_column
        effective_y = y_column if y_column != "(Contar registros)" else None

    try:
        figure = build_chart(df, chart_type, effective_x, effective_y, aggregation, top_n)
        st.plotly_chart(figure, use_container_width=True)
    except Exception as exc:
        st.warning(f"No se pudo generar el gráfico: {exc}")
        if chart_type in {"histogram", "dispersión", "heatmap"} and not numeric_cols:
            st.info("Este tipo de gráfico requiere columnas numéricas. Revisa los tipos de datos o selecciona otro gráfico.")


def render_export(df: pd.DataFrame) -> None:
    page_header("Exportar resultados", "Descarga un libro Excel con los datos originales, los datos filtrados y las salidas del análisis.")
    original_df = st.session_state.get("original_df", df)
    st.markdown(
        "<div class='bi-section'><b>Contenido del libro</b><p class='bi-muted'>Datos_originales · Datos_filtrados · "
        "Resumen estadístico · Frecuencias · Calidad por columna · Correlaciones</p></div>",
        unsafe_allow_html=True,
    )
    st.write("")
    st.metric("Registros que se exportarán en la hoja filtrada", f"{len(df):,}")
    try:
        excel_bytes = export_to_excel(original_df, df)
        st.download_button(
            label="Descargar informe Excel (.xlsx)",
            data=excel_bytes,
            file_name="reporte_dashboard_bi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"No fue posible preparar el libro Excel: {exc}")


def main() -> None:
    load_css()
    with st.sidebar:
        st.markdown('<div class="bi-brand">DataScope <span>BI</span></div>', unsafe_allow_html=True)
        st.caption("Exploración · Calidad · Estadística")
        st.divider()
        st.markdown("**1. Importar conjunto de datos**")
        uploaded_file = st.file_uploader(
            "Selecciona un archivo",
            type=["xlsx", "xls", "csv"],
            help="Se admiten archivos CSV, Excel XLSX y Excel XLS.",
        )

    if uploaded_file is None:
        show_empty_state()
        return

    file_bytes = uploaded_file.getvalue()
    fingerprint = hashlib.sha256(file_bytes).hexdigest()[:12]
    filename = uploaded_file.name
    suffix = Path(filename).suffix.lower()

    try:
        selected_sheet: str | None = None
        if suffix in {".xlsx", ".xls"}:
            sheets = cached_sheets(file_bytes, filename)
            if not sheets:
                st.error("El libro no contiene hojas disponibles.")
                return
            with st.sidebar:
                selected_sheet = st.selectbox("Hoja de Excel", sheets, key=f"sheet_{fingerprint}")
        dataset_key = f"{fingerprint}:{selected_sheet or 'csv'}"
        frame = cached_load(file_bytes, filename, selected_sheet)

        if st.session_state.get("dataset_key") != dataset_key:
            st.session_state["dataset_key"] = dataset_key
            st.session_state["original_df"] = frame.copy()
            st.session_state["working_df"] = frame.copy()

        working_df = st.session_state.get("working_df", frame).copy()
    except Exception as exc:
        st.error(f"No se pudo importar el archivo: {exc}")
        st.caption("Comprueba que el archivo no esté dañado, que tenga encabezados y que la hoja seleccionada contenga registros.")
        return

    with st.sidebar:
        st.success(f"Archivo listo · {filename}")
        st.caption(f"{len(working_df):,} filas · {len(working_df.columns):,} columnas")
        page = st.radio(
            "Navegación",
            ["Panel principal", "Explorar datos", "Calidad y limpieza", "Análisis estadístico", "Visualizaciones", "Exportar"],
            index=0,
        )

    filter_fingerprint = hashlib.sha256(dataset_key.encode("utf-8")).hexdigest()[:12]
    filters = build_sidebar_filters(working_df, filter_fingerprint)
    filtered_df = apply_filters(working_df, filters)

    if filtered_df.empty:
        st.warning("Los filtros seleccionados no devuelven registros. Ajusta los filtros del menú lateral.")
        st.metric("Registros después de filtrar", "0")
        return

    # Persistir vista filtrada para que exportación y las demás páginas usen el mismo resultado.
    st.session_state["filtered_df"] = filtered_df.copy()

    if page == "Panel principal":
        render_overview(filtered_df)
    elif page == "Explorar datos":
        render_exploration(filtered_df)
    elif page == "Calidad y limpieza":
        render_quality(working_df)
    elif page == "Análisis estadístico":
        render_statistics(filtered_df)
    elif page == "Visualizaciones":
        render_visualizations(filtered_df)
    elif page == "Exportar":
        render_export(filtered_df)

    with st.sidebar:
        st.divider()
        st.caption("DataScope BI · Procesamiento local en memoria")


if __name__ == "__main__":
    main()
