import streamlit as st
import easyocr
import tempfile
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(page_title="MedBill Guard AI", layout="centered")
st.title("🏥 MedBill Guard AI")
st.write("Upload hospital bill to generate clean digitized PDF report")

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
# CLEAN TEXT
# ==============================

def clean_text(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return lines

# ==============================
# PDF GENERATION
# ==============================

def generate_pdf(lines):

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>MedBill Guard AI - Digitized Bill Report</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Complete Extracted Bill Content</b>", styles["Heading2"]))
    elements.append(Spacer(1, 15))

    for line in lines:
        elements.append(Paragraph(line, styles["Normal"]))
        elements.append(Spacer(1, 8))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>End of Report</b>", styles["Normal"]))

    doc.build(elements)

    return temp_pdf.name

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
    cleaned_lines = clean_text(raw_text)

    pdf_path = generate_pdf(cleaned_lines)

    st.success("✅ Digitized PDF Generated Successfully")

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="⬇ Download Clean Digitized PDF",
            data=f,
            file_name="Digitized_Bill_Report.pdf",
            mime="application/pdf"
        )

    os.remove(temp_path)
