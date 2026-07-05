# ============================================================
# export_report.py — Ekspor laporan hasil analisis (Excel & PDF)
# ============================================================
import io
from datetime import datetime

import pandas as pd

from config import MODEL_METRICS


def generate_excel_report(df: pd.DataFrame, summary: dict, confidence_avg: dict) -> io.BytesIO:
    """Excel 3 sheet: Ringkasan, Data Lengkap, Top Items (100 confidence tertinggi)."""
    from utils import get_top_items

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_rows = [
            {"Metrik": "Total Data", "Nilai": summary.get("total", 0)},
            {"Metrik": "Positif", "Nilai": summary.get("positif", 0)},
            {"Metrik": "Positif (%)", "Nilai": summary.get("positif_pct", 0)},
            {"Metrik": "Negatif", "Nilai": summary.get("negatif", 0)},
            {"Metrik": "Negatif (%)", "Nilai": summary.get("negatif_pct", 0)},
            {"Metrik": "Netral", "Nilai": summary.get("netral", 0)},
            {"Metrik": "Netral (%)", "Nilai": summary.get("netral_pct", 0)},
            {"Metrik": "Rata-rata Confidence Positif (%)", "Nilai": confidence_avg.get("positive", 0)},
            {"Metrik": "Rata-rata Confidence Netral (%)", "Nilai": confidence_avg.get("neutral", 0)},
            {"Metrik": "Rata-rata Confidence Negatif (%)", "Nilai": confidence_avg.get("negative", 0)},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Ringkasan", index=False)

        df.to_excel(writer, sheet_name="Data Lengkap", index=False)

        top_items = get_top_items(df, n=100)
        pd.DataFrame(top_items).to_excel(writer, sheet_name="Top Items", index=False)

    output.seek(0)
    return output


def generate_pdf_report(df: pd.DataFrame, summary: dict, confidence_avg: dict, keyword: str = "") -> io.BytesIO:
    """PDF via ReportLab Platypus: judul, ringkasan per kelas, confidence, metrik benchmark, top-20 item."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    from utils import get_top_items

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Laporan Analisis Sentimen — SentimenS IndoBERT", styles["Title"]))
    if keyword:
        elements.append(Paragraph(f"Kata kunci: {keyword}", styles["Normal"]))
    elements.append(Paragraph(f"Dibuat: {datetime.now().strftime('%d %B %Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Ringkasan per Kelas", styles["Heading2"]))
    summary_table_data = [
        ["Kelas", "Jumlah", "Persentase"],
        ["Positif", summary.get("positif", 0), f"{summary.get('positif_pct', 0)}%"],
        ["Netral", summary.get("netral", 0), f"{summary.get('netral_pct', 0)}%"],
        ["Negatif", summary.get("negatif", 0), f"{summary.get('negatif_pct', 0)}%"],
        ["Total", summary.get("total", 0), "100%"],
    ]
    elements.append(_styled_table(summary_table_data))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Rata-rata Confidence", styles["Heading2"]))
    conf_table_data = [
        ["Kelas", "Rata-rata Confidence"],
        ["Positif", f"{confidence_avg.get('positive', 0)}%"],
        ["Netral", f"{confidence_avg.get('neutral', 0)}%"],
        ["Negatif", f"{confidence_avg.get('negative', 0)}%"],
    ]
    elements.append(_styled_table(conf_table_data))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Metrik Evaluasi Model (benchmark offline, n=1873)", styles["Heading2"]))
    elements.append(Paragraph(
        "Catatan: metrik ini adalah hasil pengujian model pada dataset berlabel terpisah, "
        "bukan akurasi dari data hasil scrape/batch ini (data tersebut tidak memiliki label asli).",
        styles["Italic"],
    ))
    metrics_table_data = [["Metrik", "Nilai (%)"]] + [
        [k.replace("_", " "), v] for k, v in MODEL_METRICS.items() if k != "per_class"
    ]
    elements.append(_styled_table(metrics_table_data))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Top 20 Item (Confidence Tertinggi)", styles["Heading2"]))
    top_items = get_top_items(df, n=20)
    top_table_data = [["Teks", "Sentimen", "Confidence"]]
    for item in top_items:
        text = str(item.get("teks_asli", ""))[:80]
        top_table_data.append([
            text,
            item.get("sentimen", ""),
            f"{round(float(item.get('confidence', 0)) * 100, 1)}%",
        ])
    elements.append(_styled_table(top_table_data, col_widths=[10 * cm, 3 * cm, 3 * cm]))

    doc.build(elements)
    output.seek(0)
    return output


def _styled_table(data, col_widths=None):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a344e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table
