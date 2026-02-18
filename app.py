import streamlit as st
import easyocr
import tempfile
import os
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from openpyxl import Workbook

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("Upload hospital bill to generate structured PDF & Excel report")

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
# SMART STRUCTURED EXTRACTION
# ==============================

def extract_structured_data(text):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    patient = "Not Detected"
    hospital = "Not Detected"
    date = "Not Detected"
    gst = 0
    total = 0
    items = []

    # -------- DATE --------
    date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
    if date_match:
        date = date_match.group(0)

    # -------- PATIENT (Search top area only) --------
    for line in lines[:15]:
        lower = line.lower()

        if "patient" in lower and "name" in lower:
            if ":" in line:
                name_part = line.split(":", 1)[1]
            else:
                name_part = re.sub(r"(?i)patient\s*name", "", line)

            name_part = re.sub(r"[^A-Za-z ]", "", name_part).strip()

            if len(name_part.split()) >= 2:
                patient = name_part
                break

    # -------- HOSPITAL (Top area only) --------
    for line in lines[:10]:
        if any(word in line.lower() for word in ["hospital", "clinic", "medical"]):
            hospital = line
            break

    # -------- GST --------
    for line in lines:
        if "gst" in line.lower():
            nums = re.findall(r"\d+\.\d+|\d+", line)
            if nums:
                gst = float(nums[-1])
                break

    # -------- TOTAL (Strict only) --------
    for line in lines:
        lower = line.lower()
        if any(word in lower for word in ["grand total", "total amount", "net total", "total"]):
            nums = re.findall(r"\d+\.\d+|\d+", line)
            if nums:
                total = float(nums[-1])
                break

    # -------- LINE ITEMS --------
    for line in lines:
        nums = re.findall(r"\d+\.\d+|\d+", line)

        if len(nums) >= 3:
            try:
                qty = int(float(nums[0]))
                unit_price = float(nums[-2])
                line_total = float(nums[-1])

                if 1 <= qty <= 100 and unit_price < 100000:
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

    elements.append(Paragraph("<b>MedBill Guard AI - Structured Report</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"<b>Patient:</b> {patient}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Hospital:</b> {hospital}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Date:</b> {date}", styles["Normal"]))
    elements.append(Paragraph(f"<b>GST:</b> {gst}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Total:</b> {total}", styles["Normal"]))
    elements.append(Spacer(1, 25))

    # Line Items Table
    if items:
        elements.append(Paragraph("<b>Extracted Line Items</b>", styles["Heading2"]))
        elements.append(Spacer(1, 10))

        table_data = [["Qty", "Item Name", "Unit Price", "Line Total"]] + items
        table = Table(table_data, repeatRows=1)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID
