from pathlib import Path
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="BYTE Data Analyst", page_icon="📊", layout="wide")
st.title("BYTE Data Analyst")
st.caption("Phase 1 · Project foundation")
st.info("Setup preview only. Analysis tools, model reasoning and memory are not implemented yet.")
with st.sidebar:
    st.header("Connection")
    st.write("Planned provider: Gemini")
    st.write("Key configured locally" if os.getenv("GEMINI_API_KEY", "").strip() else "No API key — setup preview works without one")
    st.caption("No model request is made in this version. Key presence does not verify API access.")
st.subheader("Example dataset")
st.caption("Synthetic data supplied with the project; no upload or external transfer occurs.")
df = pd.read_csv(ROOT / "data" / "demo_sales.csv")
st.dataframe(df, hide_index=True)
st.download_button("Download example CSV", df.to_csv(index=False), "demo_sales.csv", "text/csv")
st.subheader("Planned analysis tools")
for name, purpose in [
    ("Inspect dataset", "Column types, missing values and dataset structure"),
    ("Filter rows", "Retrieve records matching validated conditions"),
    ("Summarise groups", "Counts, sums, averages and rankings"),
    ("Analyse time trends", "Aggregate a chosen metric across time periods"),
    ("Measure correlations", "Numeric relationships with sample-size and missing-data reporting"),
]:
    st.write(f"**{name}** — {purpose}")
st.text_input("Ask about your dataset", disabled=True, placeholder="Enabled after the analysis engine and model are connected")
