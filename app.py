import streamlit as st
import easyocr
import tempfile
import os
import re

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
# SMART FIELD EXTRACTION
# ==============================

def extract_structured_data(text):

    lines = text.split("\n")
    text_lower = text.lower()

    patient = "Not Detected"
    hospital = "Not Detected"
    date = "Not Detected"
    gst = 0
    total = 0
    items = []

    # ---------- DATE ----------
    date_match = re.search(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        text
    )
    if date_match:
        date = date_match.group(0)

    # ---------- PATIENT ----------
    for line in lines:
        if any(word in line.lower() for word in ["patient", "name"]):
            cleaned = re.sub(r"[^A-Za-z ]", "", line)
            if len(cleaned) > 5:
                patient = cleaned.strip()
                break

    # ---------- HOSPITAL ----------
    for line in lines:
        if any(word in line.lower() for word in ["hospital", "clinic", "medical"]):
            cleaned = re.sub(r"[^A-Za-z ]", "", line)
            if len(cleaned) > 5:
                hospital = cleaned.strip()
                break

    # ---------- GST & TOTAL ----------
    for line in lines:
        lower = line.lower()
        numbers = re.findall(r"\d+\.\d+|\d+", line)
        numbers = [float(n) for n in numbers]

        if "gst" in lower or "tax" in lower:
            if numbers:
                gst = max(numbers)

        if any(word in lower for word in ["total", "grand", "net amount"]):
            if numbers:
                total = max(numbers)

    # Fallback total detection
    if total == 0:
        all_numbers = re.findall(r"\d+\.\d+|\d+", text)
        if all_numbers:
            total = max([float(n) for n in all_numbers])

    # ---------- LINE ITEMS ----------
    for line in lines:
        numbers = re.findall(r"\d+\.\d+|\d+", line)
        if len(numbers) >= 3:
            try:
                qty = int(float(numbers[0]))
                unit_price = float(numbers[-2])
                line_total = float(numbers[-1])

                if 1 <= qty <= 100 and 1 <= unit_price <= 100000:
                    name = re.sub(r"\d+\.\d+|\d+", "", line)
                    name = re.sub(r"[^A-Za-z ]", "", name).strip()

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
# VALIDATION
# ==============================

def validate_bill(data):

    errors = []
    fraud_score = 0

    if data["total"] == 0:
        errors.append("Total not detected")
        fraud_score += 30

    for item in data["items"]:
        calculated = item["quantity"] * item["unit_price"]
        if abs(calculated - item["line_total"]) > 10:
            errors.append(f"Line mismatch: {item['item_name']}")
            fraud_score += 10

    if len(data["items"]) == 0:
        errors.append("No valid line items detected")
        fraud_score += 20

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

    data = extract_structured_data(text)
    validation_errors, fraud_score = validate_bill(data)

    st.subheader("📄 Extracted Structured Data")
    st.json(data)

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
