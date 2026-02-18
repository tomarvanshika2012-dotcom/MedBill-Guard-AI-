import streamlit as st
import easyocr
import tempfile
import os
import re
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Preformatted
from reportlab.lib.units import inch
from openpyxl import Workbook

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("AI-Powered Hospital Bill OCR & Structured Extraction System")

# ==============================
# LOAD OCR
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
# DATA EXTRACTION
# ==============================

def extract_structured_data(text):

    lines = text.split("\n")
    patient = "Not Detected"
    hospital = "Not Detected"
    date = "Not Detected"
    gst = 0
    total = 0
    items = []

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

        if any(word in lower for word in ["hospital", "clinic"]):
            hospital = line.strip()

        numbers = re.findall(r"\d+\.\d+|\d+", line)
        numbers = [float(n) for n in numbers]

        if "gst" in lower and numbers:
            gst = max(numbers)

        if any(word in lower for word in ["total", "grand", "net"]) and numbers:
            total = max(numbers)

    if total == 0:
        all_numbers = re.findall(r"\d+\.\d+|\d+", text)
        if all_numbers:
            total = max([float(n) for n in all_numbers])

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
                        items.append({
                            "quantity": qty,
                            "item_name": name,
                            "unit_price": unit_price,
                            "line_total": line_total
                        })
            except:
                continue

    return {
        "patient_name": patient,
        "hospital_name": hospital,
        "date": date,
        "gst": gst,
        "total": total,
        "items": items
    }

# ==============================
# PDF GENERATION
# ==============================

def generate_pdf(data):

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>MedBill Guard AI - Extracted Report</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    formatted_json = json.dumps(data, indent=4)
    elements.append(Preformatted(formatted_json, styles["Code"]))

    doc.build(elements)
    return temp_pdf.name

# ==============================
# EXCEL GENERATION
# ==============================

def generate_excel(data):

    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted Data"

    # Header Info
    ws.append(["Patient Name", data["patient_name"]])
    ws.append(["Hospital Name", data["hospital_name"]])
    ws.append(["Date", data["date"]])
    ws.append(["GST", data["gst"]])
    ws.append(["Total", data["total"]])
    ws.append([])

    # Line Items Table
    ws.append(["Quantity", "Item Name", "Unit Price", "Line Total"])

    for item in data["items"]:
        ws.append([
            item["quantity"],
            item["item_name"],
            item["unit_price"],
            item["line_total"]
        ])

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

    st.info("🔎 Processing bill using AI OCR...")

    text = extract_text(temp_path)
    data = extract_structured_data(text)

    st.subheader("📄 Extracted Structured Data")
    st.json(data)

    # PDF Download
    pdf_path = generate_pdf(data)
    with open(pdf_path, "rb") as f:
        st.download_button(
            label="⬇ Download as PDF",
            data=f,
            file_name="extracted_report.pdf",
            mime="application/pdf"
        )

    # Excel Download
    excel_path = generate_excel(data)
    with open(excel_path, "rb") as f:
        st.download_button(
            label="⬇ Download as Excel Sheet",
            data=f,
            file_name="extracted_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    os.remove(temp_path)
