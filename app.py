import streamlit as st
import easyocr
import tempfile
import os
import re
from typing import Dict, List

# ==============================
# CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("AI-Powered Hospital Bill OCR & Validation System")

# Initialize OCR reader (loads once)
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'])

reader = load_reader()

# ==============================
# OCR FUNCTION
# ==============================

def extract_text_from_image(path):
    results = reader.readtext(path)
    return " ".join([text[1] for text in results])

# ==============================
# DATA EXTRACTION
# ==============================

def extract_line_items(text: str):
    items = []
    pattern = r"(\d+)\s+([A-Za-z ]+)\s+(\d+\.?\d*)\s+(\d+\.?\d*)"
    matches = re.findall(pattern, text)

    for match in matches:
        items.append({
            "quantity": int(match[0]),
            "item_name": match[1].strip(),
            "unit_price": float(match[2]),
            "line_total": float(match[3])
        })

    return items

def extract_key_details(text: str):
    patient = re.search(r"Patient Name[:\-]?\s*(.*)", text)
    hospital = re.search(r"Hospital Name[:\-]?\s*(.*)", text)
    date = re.search(r"Date[:\-]?\s*(.*)", text)
    gst = re.search(r"GST[:\-]?\s*(\d+\.?\d*)", text)
    total = re.search(r"Total[:\-]?\s*(\d+\.?\d*)", text)

    return {
        "patient_name": patient.group(1).strip() if patient else "Not Found",
        "hospital_name": hospital.group(1).strip() if hospital else "Not Found",
        "date": date.group(1).strip() if date else "Not Found",
        "gst": float(gst.group(1)) if gst else 0,
        "total": float(total.group(1)) if total else 0
    }

# ==============================
# VALIDATION ENGINE
# ==============================

def validate_bill(data: Dict, items: List[Dict], text: str):
    errors = []
    fraud_score = 0

    # Missing fields
    for key, value in data.items():
        if value in ["Not Found", "", 0]:
            errors.append(f"Missing or invalid {key}")
            fraud_score += 15

    # GST validation (18%)
    subtotal_match = re.search(r"Sub Total[:\-]?\s*(\d+\.?\d*)", text)
    if subtotal_match:
        subtotal = float(subtotal_match.group(1))
        expected_gst = subtotal * 0.18
        if abs(expected_gst - data["gst"]) > 5:
            errors.append("GST calculation mismatch")
            fraud_score += 25

    # Duplicate items
    item_names = [item["item_name"] for item in items]
    if len(item_names) != len(set(item_names)):
        errors.append("Duplicate billing items detected")
        fraud_score += 20

    # Line total validation
    for item in items:
        calculated = item["quantity"] * item["unit_price"]
        if abs(calculated - item["line_total"]) > 2:
            errors.append(f"Line total mismatch for {item['item_name']}")
            fraud_score += 15

    return errors, min(fraud_score, 100)

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

    st.info("Processing bill using AI OCR...")

    text = extract_text_from_image(temp_path)

    extracted_data = extract_key_details(text)
    line_items = extract_line_items(text)
    validation_errors, fraud_score = validate_bill(extracted_data, line_items, text)

    st.subheader("📄 Extracted Data")
    st.json(extracted_data)

    st.subheader("📦 Line Items")
    st.json(line_items)

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
