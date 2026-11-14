# DataScope BI — Dashboard analítico en Python

Aplicación web genérica para cargar archivos CSV y Excel, revisar su calidad, limpiar datos, calcular estadísticas, crear gráficos interactivos y exportar resultados a un libro Excel.

> **Los datos del panel no están precargados.** Los KPI y los gráficos se calculan a partir del archivo que cargue el usuario. `ejemplo_datos.csv` es un archivo pequeño de demostración con datos sintéticos, incluido únicamente para probar la instalación y las funciones; no se usa automáticamente ni representa resultados reales.

## 1. Características

- Importación de `.xlsx`, `.xls` y `.csv`.
- Selección de hojas en libros Excel.
- Detección de separador y codificación habituales en CSV.
- Panel con registros, columnas, nulos, duplicados y perfil de tipos.
- Filtros globales para rangos numéricos, fechas y categorías de cardinalidad moderada.
- Limpieza opcional de espacios, cadenas vacías, duplicados y columnas vacías.
- Conversión prudente de columnas de texto a número y fechas, cuando el usuario la activa.
- Estadísticas: conteo, media, mediana, moda, desviación estándar, mínimo y máximo.
- Frecuencias, porcentajes y correlaciones de Pearson.
- Gráficos Plotly: barras, líneas, circular, histograma, dispersión y mapa de calor.
- Exportación Excel con hojas separadas y formato básico de presentación.
- Caché de carga para evitar releer el mismo archivo en cada interacción.
- Procesamiento local en memoria; no requiere base de datos externa.

## 2. Estructura del proyecto

```text
dashboard_bi/
├── app.py
├── requirements.txt
├── README.md
├── ejemplo_datos.csv
├── modules/
│   ├── __init__.py
│   ├── loader.py
│   ├── processor.py
│   ├── analytics.py
│   ├── charts.py
│   └── exporter.py
├── assets/
│   └── styles.css
├── .streamlit/
│   └── config.toml
├── exports/
└── tests/
    └── smoke_test.py
```

La carpeta `exports/` se reserva para archivos que se quieran guardar manualmente. La descarga generada desde la aplicación se entrega directamente al navegador y no necesita escribir archivos en esa carpeta.

## 3. Instalación en Windows

Se recomienda Python 3.10 o superior.

1. Descomprime la carpeta `dashboard_bi` y abre CMD o PowerShell en esa ubicación.
2. Crea un entorno virtual:

   ```powershell
   py -m venv .venv
   ```

3. Activa el entorno:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   En CMD puedes usar:

   ```cmd
   .venv\Scripts\activate.bat
   ```

4. Actualiza pip e instala las dependencias:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. Inicia la aplicación:

   ```powershell
   streamlit run app.py
   ```

6. Streamlit abrirá el dashboard en el navegador. Si no lo hace automáticamente, visita `http://localhost:8501`.

Para detener el servidor, vuelve a la terminal y presiona `Ctrl + C`.

## 4. Uso básico

1. En el menú lateral, selecciona un archivo `.xlsx`, `.xls` o `.csv`.
2. Si es un libro Excel, selecciona la hoja que contiene los datos.
3. El panel muestra los indicadores calculados sobre el conjunto cargado.
4. Usa los filtros del menú lateral; las páginas de estadísticas y visualizaciones se actualizan con los mismos filtros.
5. En **Calidad y limpieza**, selecciona las operaciones deseadas y pulsa **Aplicar limpieza**. La aplicación conserva la versión cargada para poder restablecerla.
6. En **Exportar**, descarga un libro con las hojas de datos, resumen, frecuencias, calidad y correlaciones.

## 5. Explicación de los módulos

| Archivo | Responsabilidad |
|---|---|
| `app.py` | Interfaz Streamlit, navegación, estado de sesión, filtros globales y coordinación de módulos. |
| `modules/loader.py` | Valida extensiones, lee CSV y hojas Excel, hace encabezados únicos y devuelve un DataFrame. |
| `modules/processor.py` | Perfil de columnas, inferencia prudente de tipos, limpieza, filtros y agrupaciones. |
| `modules/analytics.py` | KPI generales, estadísticas descriptivas, frecuencias, valores faltantes y correlaciones. |
| `modules/charts.py` | Construye visualizaciones Plotly según las columnas elegidas. |
| `modules/exporter.py` | Genera el Excel de salida y aplica formato con OpenPyXL. |
| `assets/styles.css` | Estilos oscuros, tarjetas, bordes, estados hover y ajustes responsive. |
| `.streamlit/config.toml` | Tema oscuro y configuración del servidor Streamlit. |

## 6. Compatibilidad de XLS, XLSX y CSV

- **XLSX:** Pandas utiliza `openpyxl` como motor de lectura y escritura.
- **XLS:** OpenPyXL no lee el formato binario antiguo `.xls`. Por eso, la aplicación utiliza `xlrd>=2.0.1` para leerlo. La exportación se realiza siempre a `.xlsx` con OpenPyXL.
- **CSV:** se intenta detectar el delimitador y se prueban codificaciones comunes (`UTF-8`, `Windows-1252` y `Latin-1`). Si el archivo utiliza una codificación o delimitador poco habitual, conviene guardarlo como UTF-8.

## 7. Decisiones y límites conocidos

- La aplicación no crea KPI de negocio arbitrarios: muestra indicadores estructurales y estadísticas que se pueden calcular de forma genérica a partir de los datos disponibles.
- Los valores faltantes se mantienen en los datos hasta que el usuario elija una operación; no se imputan automáticamente.
- La inferencia de tipos es opcional. Se evita convertir de manera automática identificadores con ceros a la izquierda.
- Los filtros categóricos aparecen para columnas de hasta 80 categorías para mantener una interfaz manejable. Las demás columnas siguen disponibles para exploración y gráficos.
- La correlación usa Pearson y solo considera variables numéricas. Correlación no equivale a causalidad.
- Los datos permanecen en memoria durante la sesión de Streamlit; no se guardan en una base de datos.
- Para archivos muy grandes, el rendimiento depende de la memoria disponible en el equipo y del volumen de datos que Plotly deba representar.

## 8. Pruebas rápidas

Con el entorno virtual activado, ejecuta:

```powershell
python -m unittest discover -s tests -v
```

Para verificar la aplicación completa en modo servidor:

```powershell
streamlit run app.py --server.headless true
```

Luego abre `http://localhost:8501`, carga `ejemplo_datos.csv`, prueba los filtros y genera un archivo desde **Exportar**.

## 9. Dependencias

Las dependencias directas están listadas en `requirements.txt`: pandas, NumPy, OpenPyXL, Plotly, Streamlit y xlrd. `xlrd` se incluye exclusivamente para dar soporte de lectura al formato `.xls`.
