import streamlit as st
import easyocr
import tempfile
import os
import re
from typing import Dict, List

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("AI-Powered Hospital Bill OCR & Smart Validation System")

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
# SMART FIELD EXTRACTION
# ==============================

def extract_key_details(text: str):

    text_lower = text.lower()
    lines = text.split("\n")

    date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)

    gst = 0
    total = 0

    for line in lines:
        line_lower = line.lower()

        # Detect GST line
        if "gst" in line_lower:
            numbers = re.findall(r"\d+\.\d+|\d+", line)
            if numbers:
                gst = float(numbers[-1])

        # Detect Total line
        if "total" in line_lower and "sub" not in line_lower:
            numbers = re.findall(r"\d+\.\d+|\d+", line)
            if numbers:
                total = float(numbers[-1])

    return {
        "patient_name": "Not Detected",
        "hospital_name": "Not Detected",
        "date": date_match.group(0) if date_match else "Not Detected",
        "gst": gst,
        "total": total
    }

# ==============================
# LINE ITEM EXTRACTION (SAFER)
# ==============================

def extract_line_items(text: str):

    items = []
    lines = text.split("\n")

    for line in lines:
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        # Must have at least 3 numbers (qty, price, total)
        if len(numbers) >= 3:
            try:
                qty = int(float(numbers[0]))
                unit_price = float(numbers[-2])
                line_total = float(numbers[-1])

                # Extract name (remove numbers from line)
                name = re.sub(r"\d+\.\d+|\d+", "", line).strip()

                if len(name) > 2:
                    items.append({
                        "quantity": qty,
                        "item_name": name,
                        "unit_price": unit_price,
                        "line_total": line_total
                    })
            except:
                continue

    return items

# ==============================
# VALIDATION ENGINE (BALANCED)
# ==============================

def validate_bill(data: Dict, items: List[Dict], text: str):

    errors = []
    fraud_score = 0

    # Total missing
    if data["total"] == 0:
        errors.append("Total amount not detected")
        fraud_score += 30

    # GST mismatch (if subtotal present)
    subtotal_match = re.search(r"sub\s*total.*?(\d+\.?\d*)", text.lower())
    if subtotal_match and data["gst"] > 0:
        subtotal = float(subtotal_match.group(1))
        expected_gst = subtotal * 0.18
        if abs(expected_gst - data["gst"]) > 5:
            errors.append("GST calculation mismatch")
            fraud_score += 20

    # Line total validation
    for item in items:
        calculated = item["quantity"] * item["unit_price"]
        if abs(calculated - item["line_total"]) > 2:
            errors.append(f"Line mismatch: {item['item_name']}")
            fraud_score += 10

    # Duplicate items
    names = [item["item_name"] for item in items]
    if len(names) != len(set(names)):
        errors.append("Duplicate items detected")
        fraud_score += 10

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

    st.info("🔎 Processing bill using AI OCR...")

    text = extract_text(temp_path)

    extracted_data = extract_key_details(text)
    line_items = extract_line_items(text)
    validation_errors, fraud_score = validate_bill(extracted_data, line_items, text)

    st.subheader("📄 Extracted Data")
    st.json(extracted_data)

    st.subheader("📦 Line Items")
    st.json(line_items)

    st.subheader("🔍 Validation Results")

    if validation_errors:
        st.warning(validation_errors)
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
