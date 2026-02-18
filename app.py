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
# SMART LINE ITEM FILTER
# ==============================

def extract_line_items(text):

    items = []
    lines = text.split("\n")

    for line in lines:

        # Must contain at least 3 numbers
        numbers = re.findall(r"\d+\.\d+|\d+", line)
        if len(numbers) < 3:
            continue

        try:
            qty = int(float(numbers[0]))
            unit_price = float(numbers[-2])
            total = float(numbers[-1])

            # Strict realistic filters
            if not (1 <= qty <= 100):
                continue

            if not (1 <= unit_price <= 100000):
                continue

            if not (1 <= total <= 1000000):
                continue

            # Extract name safely
            name = re.sub(r"\d+\.\d+|\d+", "", line)
            name = re.sub(r"[^A-Za-z ]", "", name).strip()

            if len(name) < 4:
                continue

            # Reject garbage names
            if any(char in name for char in ["[", "]", "/", "-", "#"]):
                continue

            items.append({
                "quantity": qty,
                "item_name": name,
                "unit_price": unit_price,
                "line_total": total
            })

        except:
            continue

    return items

# ==============================
# TOTAL EXTRACTION (SAFE)
# ==============================

def extract_total(text):

    lines = text.split("\n")

    for line in lines:
        if any(word in line.lower() for word in ["total", "grand", "net amount"]):
            numbers = re.findall(r"\d+\.\d+|\d+", line)
            if numbers:
                return float(numbers[-1])

    # fallback: highest number
    all_numbers = re.findall(r"\d+\.\d+|\d+", text)
    if all_numbers:
        return max([float(n) for n in all_numbers])

    return 0

# ==============================
# VALIDATION
# ==============================

def validate_bill(total, items):

    errors = []
    fraud_score = 0

    if total == 0:
        errors.append("Total amount not detected")
        fraud_score += 30

    for item in items:
        calculated = item["quantity"] * item["unit_price"]

        # Larger tolerance to avoid OCR noise
        if abs(calculated - item["line_total"]) > 10:
            errors.append(f"Line mismatch: {item['item_name']}")
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

    total = extract_total(text)
    line_items = extract_line_items(text)
    validation_errors, fraud_score = validate_bill(total, line_items)

    st.subheader("📄 Extracted Total")
    st.write(f"Detected Total: ₹ {total}")

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
