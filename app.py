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
# LOAD OCR
# ==============================

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'])

reader = load_reader()

# ==============================
# OCR
# ==============================

def extract_text(path):
    results = reader.readtext(path)
    return "\n".join([text[1] for text in results])

# ==============================
# SMART FIELD EXTRACTION
# ==============================

def extract_key_details(text: str):

    lines = text.split("\n")
    text_lower = text.lower()

    # DATE detection (multiple formats)
    date_match = re.search(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        text
    )

    total = 0
    gst = 0

    for line in lines:
        lower = line.lower()

        numbers = re.findall(r"\d+\.\d+|\d+", line)
        numbers = [float(n) for n in numbers]

        # Detect total using keywords
        if any(word in lower for word in ["total", "grand", "amount", "net"]):
            if numbers:
                total = max(numbers)

        # Detect GST
        if "gst" in lower or "tax" in lower:
            if numbers:
                gst = max(numbers)

    # Fallback: if total still zero, pick largest number in document
    if total == 0:
        all_numbers = re.findall(r"\d+\.\d+|\d+", text)
        all_numbers = [float(n) for n in all_numbers]
        if all_numbers:
            total = max(all_numbers)

    return {
        "patient_name": "Auto Detection Limited",
        "hospital_name": "Auto Detection Limited",
        "date": date_match.group(0) if date_match else "Not Detected",
        "gst": gst,
        "total": total
    }

# ==============================
# LINE ITEM EXTRACTION (IMPROVED)
# ==============================

def extract_line_items(text: str):

    items = []
    lines = text.split("\n")

    for line in lines:
        numbers = re.findall(r"\d+\.\d+|\d+", line)

        if len(numbers) >= 2:
            try:
                qty = int(float(numbers[0]))
                unit_price = float(numbers[-2])
                line_total = float(numbers[-1])

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

    return items

# ==============================
# VALIDATION
# ==============================

def validate_bill(data: Dict, items: List[Dict], text: str):

    errors = []
    fraud_score = 0

    if data["total"] == 0:
        errors.append("Total amount not detected")
        fraud_score += 30

    for item in items:
        calculated = item["quantity"] * item["unit_price"]

        # Allow small OCR tolerance
        if abs(calculated - item["line_total"]) > 5:
            errors.append(f"Line mismatch: {item['item_name']}")
            fraud_score += 10

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
