# app.py
import streamlit as st
import os
import openai
from io import BytesIO
from PyPDF2 import PdfReader
import textwrap

st.set_page_config(page_title="Tiny RFP Assistant", layout="wide")
st.title("🧾 Tiny RFP Assistant — Paste or upload a PDF")

# Get API key from env or Streamlit secrets
OPENAI_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
if not OPENAI_KEY:
    st.warning("No OPENAI_API_KEY found. Add your key in Streamlit Secrets (or set OPENAI_API_KEY).")
    st.stop()

openai.api_key = OPENAI_KEY

def extract_text_from_pdf(file_bytes):
    try:
        reader = PdfReader(BytesIO(file_bytes))
        text = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text.append(page_text)
        return "\n\n".join(text)
    except Exception as e:
        return ""

st.markdown("**How to use:** Paste RFP text in the box OR upload a PDF file. Click *Generate Draft Answers*. Share the Streamlit URL with teammates.")

col1, col2 = st.columns([2,1])
with col1:
    text_input = st.text_area("Paste RFP text (or paste extracted questions)", height=300, placeholder="Paste the RFP or its questions here...")
    uploaded = st.file_uploader("Or upload RFP PDF", type=["pdf","txt"])
with col2:
    st.markdown("### Options")
    model = st.selectbox("Model (choose one)", ["gpt-3.5-turbo","gpt-4o-mini"], index=0)
    temperature = st.slider("Creativity (temperature)", 0.0, 1.0, 0.2, 0.05)
    max_tokens = st.slider("Max tokens", 200, 2000, 1000, 50)

if uploaded is not None:
    raw = uploaded.read()
    if uploaded.type == "application/pdf":
        extracted = extract_text_from_pdf(raw)
        if not extracted.strip():
            st.error("Couldn't extract text from PDF (try a different PDF).")
        else:
            # show a preview and put into text area
            preview = extracted[:4000]
            st.info("Extracted text preview (first 4k chars):")
            st.code(preview)
            # populate text_input with extracted
            if not text_input:
                text_input = extracted

if not text_input or text_input.strip()=="":
    st.warning("Please paste RFP text or upload a PDF.")
    st.stop()

prompt = f"""
You are an RFP assistant. Given the RFP text below, do the following:
1) Provide a short "RFP at a glance" summary in 3-5 bullet points.
2) Extract up to 12 clear questions or requirement bullets (numbered).
3) For each question/bullet, propose a concise draft answer (2-6 sentences) tailored for a professional B2B vendor response.
4) Note any obvious missing information we should ask the buyer.
Output JSON with fields: summary (array of bullets), items (array of {{question, draft_answer}}), missing_info (array).
Respond only with valid JSON.
RFP_TEXT:
\"\"\"{textwrap.shorten(text_input, width=15000, placeholder='...') }\"\"\"
"""

if st.button("Generate Draft Answers"):
    with st.spinner("Asking the model..."):
        try:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role":"system","content":"You are a helpful, professional RFP response assistant."},
                          {"role":"user","content":prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            out = resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            st.stop()

    st.success("Done — model returned results.")
    st.subheader("Raw model output (JSON)")
    st.code(out, language="json")

    # also try to pretty-print parsed JSON if possible
    import json
    try:
        parsed = json.loads(out)
        st.subheader("Summary")
        for b in parsed.get("summary", []):
            st.write("•", b)
        st.subheader("Extracted questions and draft answers")
        for idx, it in enumerate(parsed.get("items", [])[:50], 1):
            st.markdown(f"**{idx}. {it.get('question','(no question)')}**")
            st.write(it.get("draft_answer",""))
        if parsed.get("missing_info"):
            st.subheader("Missing / follow-up info to request")
            for m in parsed.get("missing_info", []):
                st.write("•", m)
    except Exception:
        st.info("Could not parse JSON automatically; view raw output above.")

    # allow download
    st.download_button("Download result (txt)", data=out, file_name="rfp_draft_response.txt")
