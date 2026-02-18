import streamlit as st
import easyocr
import tempfile
import os
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from openpyxl import Workbook

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("Upload hospital bill to generate structured PDF & Excel report")

# ==============================
# LOAD OCR MODEL
# ==============================

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'])

reader = load_reader()

# ==============================
# OCR FUNCTION
# ==============================

def extract_text(path):
    results = reader.readtext(path)
    return "\n".join([text[1] for text in results])

# ==============================
# STRUCTURED DATA EXTRACTION
# ==============================

def extract_structured_data(text):

    lines = text.split("\n")
    patient = "Not Detected"
    hospital = "Not Detected"
    date = "Not Detected"
    gst = 0
    total = 0
    items = []

    # Date detection
    date_match = re.search(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        text
    )
    if date_match:
        date = date_match.group(0)

    for line in lines:
        lower = line.lower()

        if "patient" in lower:
            patient = line.strip()

        if any(word in lower for word in ["hospital", "clinic", "medical"]):
            hospital = line.strip()

        numbers = re.findall(r"\d+\.\d+|\d+", line)
        numbers = [float(n) for n in numbers]

        if "gst" in lower and numbers:
            gst = max(numbers)

        if any(word in lower for word in ["total", "grand", "net"]) and numbers:
            total = max(numbers)

    # Fallback total
    if total == 0:
        all_numbers = re.findall(r"\d+\.\d+|\d+", text)
        if all_numbers:
            total = max([float(n) for n in all_numbers])

    # Line Items
    for line in lines:
        numbers = re.findall(r"\d+\.\d+|\d+", line)
        if len(numbers) >= 3:
            try:
                qty = int(float(numbers[0]))
                unit_price = float(numbers[-2])
                line_total = float(numbers[-1])

                if 1 <= qty <= 100:
                    name = re.sub(r"\d+\.\d+|\d+", "", line).strip()
                    if len(name) > 3:
                        items.append([
                            qty,
                            name,
                            unit_price,
                            line_total
                        ])
            except:
                continue

    return patient, hospital, date, gst, total, items

# ==============================
# PDF GENERATION
# ==============================

def generate_pdf(patient, hospital, date, gst, total, items, raw_text):

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("<b>MedBill Guard AI - Structured Report</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Structured Info
    elements.append(Paragraph(f"<b>Patient:</b> {patient}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Hospital:</b> {hospital}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Date:</b> {date}", styles["Normal"]))
    elements.append(Paragraph(f"<b>GST:</b> {gst}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Total:</b> {total}", styles["Normal"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Line Items Table
    if items:
        elements.append(Paragraph("<b>Extracted Line Items</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.2 * inch))

        table_data = [["Qty", "Item Name", "Unit Price", "Line Total"]] + items
        table = Table(table_data, repeatRows=1)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))

    # OCR Raw Text Table
    elements.append(Paragraph("<b>Original Extracted Bill Text (Table View)</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    raw_lines = raw_text.split("\n")
    raw_table_data = [["Line No", "OCR Text"]]

    for idx, line in enumerate(raw_lines, start=1):
        raw_table_data.append([str(idx), line])

    raw_table = Table(raw_table_data, repeatRows=1, colWidths=[50, 450])

    raw_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))

    elements.append(raw_table)

    doc.build(elements)
    return temp_pdf.name

# ==============================
# EXCEL GENERATION
# ==============================

def generate_excel(patient, hospital, date, gst, total, items):

    wb = Workbook()
    ws = wb.active
    ws.title = "Bill Data"

    ws.append(["Patient Name", patient])
    ws.append(["Hospital Name", hospital])
    ws.append(["Date", date])
    ws.append(["GST", gst])
    ws.append(["Total", total])
    ws.append([])

    ws.append(["Quantity", "Item Name", "Unit Price", "Line Total"])

    for item in items:
        ws.append(item)

    temp_excel = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    wb.save(temp_excel.name)

    return temp_excel.name

# ==============================
# UI
# ==============================

uploaded_file = st.file_uploader(
    "Upload Hospital Bill (Image Only)",
    type=["png", "jpg", "jpeg"]
)

if uploaded_file:

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    st.info("🔎 Processing bill...")

    raw_text = extract_text(temp_path)
    patient, hospital, date, gst, total, items = extract_structured_data(raw_text)

    pdf_path = generate_pdf(patient, hospital, date, gst, total, items, raw_text)
    excel_path = generate_excel(patient, hospital, date, gst, total, items)

    st.success("✅ Report Generated Successfully")

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="⬇ Download PDF Report",
            data=f,
            file_name="MedBill_Report.pdf",
            mime="application/pdf"
        )

    with open(excel_path, "rb") as f:
        st.download_button(
            label="⬇ Download Excel Sheet",
            data=f,
            file_name="MedBill_Data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    os.remove(temp_path)
