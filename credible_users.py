import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Airtable Embed", layout="wide")
st.title("Airtable Embed")

# Pull the embed URL from Streamlit Cloud Secrets
if "AIRTABLE_EMBED_URL" not in st.secrets:
    st.error("Missing secret: AIRTABLE_EMBED_URL. Add it under Settings → Secrets in Streamlit Cloud.")
    st.stop()

EMBED_URL = st.secrets["AIRTABLE_EMBED_URL"]

# Show the Airtable embed
components.html(
    f'<iframe src="{EMBED_URL}" width="100%" height="700" style="border:1px solid #ddd;"></iframe>',
    height=720,
)

st.caption("This is a live Airtable view embedded in Streamlit.")
