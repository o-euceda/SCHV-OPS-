from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Dict, Any

import pandas as pd


def export_flight_report(rows: Iterable[Dict[str, Any]], output_path: str | Path) -> str:
    """Genera un archivo Excel con formato profesional para un reporte de horas de vuelo."""
    df = pd.DataFrame(list(rows))

    if df.empty:
        df = pd.DataFrame(
            columns=[
                "Fecha",
                "Misión",
                "Aeronave",
                "Piloto",
                "Copiloto",
                "Origen",
                "Destino",
                "Hora Salida",
                "Hora Llegada",
                "Tiempo Total",
                "Diurna",
                "Nocturna",
                "NVG",
                "Instrumentos",
            ]
        )

    # Normalizar nombres de columnas para reportes estándar
    column_map = {
        "fecha": "Fecha",
        "fecha_salida": "Fecha",
        "codigo_mision": "Misión",
        "codigo": "Misión",
        "matricula": "Aeronave",
        "modelo": "Aeronave",
        "piloto": "Piloto",
        "copiloto": "Copiloto",
        "origen": "Origen",
        "destino": "Destino",
        "hora_salida": "Hora Salida",
        "hora_llegada": "Hora Llegada",
        "tiempo_total": "Tiempo Total",
        "tot_horas": "Tiempo Total",
        "diurna": "Diurna",
        "nocturna": "Nocturna",
        "nvg": "NVG",
        "instrumentos": "Instrumentos",
    }

    df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

    for col in ["Tiempo Total", "Diurna", "Nocturna", "NVG", "Instrumentos"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%d/%m/%Y")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reporte Horas")

        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        sheet = writer.sheets["Reporte Horas"]

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1F4E78")
        thin = Side(style="thin", color="D9D9D9")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for cell in sheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        for column_cells in sheet.columns:
            max_length = 0
            column = column_cells[0].column_letter
            for cell in column_cells:
                value = cell.value
                if value is not None:
                    max_length = max(max_length, len(str(value)))
            adjusted_width = max(max_length + 2, 12)
            sheet.column_dimensions[column].width = adjusted_width

        if not df.empty:
            total_row = sheet.max_row + 2
            for col in ["Tiempo Total", "Diurna", "Nocturna", "NVG", "Instrumentos"]:
                if col in df.columns:
                    col_index = df.columns.get_loc(col) + 1
                    label_cell = sheet.cell(row=total_row, column=1)
                    label_cell.value = "TOTAL"
                    label_cell.font = Font(bold=True)
                    label_cell.fill = PatternFill("solid", fgColor="D9EAF7")

                    total_value_cell = sheet.cell(row=total_row, column=col_index)
                    total_value_cell.value = df[col].sum()
                    total_value_cell.font = Font(bold=True)
                    total_value_cell.number_format = "0.00"
                    total_value_cell.fill = PatternFill("solid", fgColor="EAF2F8")

            for cell in sheet[total_row]:
                cell.border = border

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    return str(output)
