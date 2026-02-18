import streamlit as st
import os
import tempfile
import re
from typing import Dict
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")

st.title("🏥 MedBill Guard AI")
st.write("Real-Time Hospital Bill OCR & Validation System")

# ==============================
# OCR FUNCTIONS (Backend Logic)
# ==============================

def extract_text_from_image(image_path):
    img = Image.open(image_path)
    return pytesseract.image_to_string(img)

def extract_text_from_pdf(pdf_path):
    pages = convert_from_path(pdf_path)
    text = ""
    for page in pages:
        text += pytesseract.image_to_string(page)
    return text

# ==============================
# DATA EXTRACTION
# ==============================

def extract_key_details(text: str) -> Dict:
    patient = re.search(r"Patient Name[:\-]\s*(.*)", text)
    hospital = re.search(r"Hospital Name[:\-]\s*(.*)", text)
    date = re.search(r"Date[:\-]\s*(.*)", text)
    gst = re.search(r"GST[:\-]?\s*(\d+\.?\d*)", text)
    total = re.search(r"Total[:\-]?\s*(\d+\.?\d*)", text)

    return {
        "patient_name": patient.group(1) if patient else "Not Found",
        "hospital_name": hospital.group(1) if hospital else "Not Found",
        "date": date.group(1) if date else "Not Found",
        "gst": float(gst.group(1)) if gst else 0,
        "total": float(total.group(1)) if total else 0
    }

# ==============================
# VALIDATION ENGINE
# ==============================

def validate_bill(data: Dict, text: str):
    errors = []
    fraud_score = 0

    # Missing Fields
    for field, value in data.items():
        if value in ["Not Found", "", 0]:
            errors.append(f"Missing or invalid {field}")
            fraud_score += 20

    # GST validation (18%)
    amount_match = re.search(r"Sub Total[:\-]?\s*(\d+\.?\d*)", text)
    if amount_match:
        subtotal = float(amount_match.group(1))
        expected_gst = subtotal * 0.18
        if abs(expected_gst - data["gst"]) > 5:
            errors.append("GST calculation mismatch")
            fraud_score += 30

    # Duplicate items detection
    items = re.findall(r"\d+\s+[A-Za-z ]+\s+\d+\.?\d*", text)
    if len(items) != len(set(items)):
        errors.append("Duplicate billing items detected")
        fraud_score += 25

    return errors, min(fraud_score, 100)

# ==============================
# FILE UPLOAD UI
# ==============================

uploaded_file = st.file_uploader(
    "Upload Hospital Bill (PDF / Image)",
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file:

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(uploaded_file.read())
        temp_path = temp.name

    st.info("Processing Bill...")

    if uploaded_file.name.endswith(".pdf"):
        text = extract_text_from_pdf(temp_path)
    else:
        text = extract_text_from_image(temp_path)

    extracted_data = extract_key_details(text)
    validation_errors, fraud_score = validate_bill(extracted_data, text)

    st.subheader("📄 Extracted Data")
    st.json(extracted_data)

    st.subheader("🔍 Validation Results")

    if validation_errors:
        st.error(validation_errors)
    else:
        st.success("Bill validated successfully!")

    st.subheader("🚨 Fraud Risk Score")
    st.progress(fraud_score)

    if fraud_score < 30:
        st.success("Low Risk")
    elif fraud_score < 70:
        st.warning("Medium Risk")
    else:
        st.error("High Risk")

    os.remove(temp_path)