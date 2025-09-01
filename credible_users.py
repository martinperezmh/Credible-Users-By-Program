import os
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import altair as alt

st.set_page_config(page_title="Airtable Embed + Program Users", layout="wide")
st.title("Airtable Embed + Program Users")

# -------- config loader: Streamlit Cloud secrets first, then ENV fallback --------
REQUIRED_KEYS = ["AIRTABLE_PAT", "AIRTABLE_BASE", "AIRTABLE_TABLE", "AIRTABLE_VIEW", "AIRTABLE_EMBED_URL"]

def load_cfg():
    cfg = {}
    # Try Streamlit Cloud secrets (may raise if no local secrets.toml)
    try:
        # Access once inside try; if it fails, we'll fall back to env vars
        for k in REQUIRED_KEYS:
            if k in st.secrets:
                cfg[k] = st.secrets[k]
    except Exception:
        pass
    # Fallback to environment variables for any missing keys (local dev)
    for k in REQUIRED_KEYS:
        if k not in cfg and os.getenv(k):
            cfg[k] = os.getenv(k)
    return cfg

cfg = load_cfg()
missing = [k for k in REQUIRED_KEYS if k not in cfg]
if missing:
    st.error(
        "Missing configuration: " + ", ".join(missing) +
        "\n\nFix locally by either:\n"
        "• Adding a local `.streamlit/secrets.toml` (kept out of Git), or\n"
        "• Setting environment variables for those keys.\n\n"
        "On Streamlit Cloud, add them under Settings → Secrets."
    )
    st.stop()

PAT       = cfg["AIRTABLE_PAT"]
BASE_ID   = cfg["AIRTABLE_BASE"]
TABLE     = cfg["AIRTABLE_TABLE"]
VIEW_NAME = cfg["AIRTABLE_VIEW"]
EMBED_URL = cfg["AIRTABLE_EMBED_URL"]

# Hard-code your field names (adjust if needed)
PROGRAM_FIELD = "Program Name"
USERS_FIELD   = "Credible Users"

# -------- UI layout --------
left, right = st.columns([2, 1], gap="large")
with left:
    st.subheader("Embedded Airtable View")
    components.html(
        f'<iframe src="{EMBED_URL}" width="100%" height="700" style="border:1px solid #ddd;"></iframe>',
        height=720,
    )
    st.caption("Pie chart uses the exact same Airtable view.")

with right:
    st.subheader("Chart Options")
    PROGRAM_FIELD = st.text_input("Program field", value=PROGRAM_FIELD)
    USERS_FIELD   = st.text_input("Users metric field", value=USERS_FIELD)

# -------- fetch ONLY the embed's view --------
@st.cache_data(show_spinner=True)
def fetch_view_records(pat: str, base_id: str, table: str, view_name: str) -> pd.DataFrame:
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table)}"
    headers = {"Authorization": f"Bearer {pat}"}
    params = {"view": view_name}
    out = []
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 401:
            st.error("401 Unauthorized: check your Airtable PAT.")
            return pd.DataFrame()
        if r.status_code == 403:
            st.error("403 Forbidden: ensure PAT has 'data.records:read' and access to this base.")
            return pd.DataFrame()
        if r.status_code == 404:
            st.error("404 Not Found: check BASE, TABLE, and VIEW names.")
            return pd.DataFrame()
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("records", []))
        if "offset" in data:
            params["offset"] = data["offset"]
        else:
            break
    return pd.json_normalize([rec.get("fields", {}) for rec in out])

df = fetch_view_records(PAT, BASE_ID, TABLE, VIEW_NAME)

st.subheader(f"Credible Users by Program — View: {VIEW_NAME}")
if df.empty:
    st.info("This view returned no rows (or failed to fetch).")
elif PROGRAM_FIELD not in df.columns or USERS_FIELD not in df.columns:
    st.warning(f"Missing fields: {PROGRAM_FIELD!r} and/or {USERS_FIELD!r}. Columns: {list(df.columns)}")
else:
    dfx = df[[PROGRAM_FIELD, USERS_FIELD]].copy()
    dfx[USERS_FIELD] = pd.to_numeric(dfx[USERS_FIELD], errors="coerce").fillna(0)

    chart_df = (
        dfx.groupby(PROGRAM_FIELD, dropna=False)[USERS_FIELD]
           .sum()
           .reset_index()
           .rename(columns={PROGRAM_FIELD: "program", USERS_FIELD: "users"})
           .sort_values("users", ascending=False)
    )

    # allow selecting subset; pie recomputes % off selection
    selected = st.multiselect(
        "Programs to include (from this view)",
        options=chart_df["program"].tolist(),
        default=chart_df["program"].tolist()
    )
    if not selected:
        st.info("Select at least one program.")
        st.stop()

    filtered = chart_df[chart_df["program"].isin(selected)].copy()
    total = filtered["users"].sum()
    if total == 0:
        st.info("Selected programs sum to zero users.")
        st.stop()

    filtered["percent"] = filtered["users"] / total
    filtered["percent_label"] = (filtered["percent"] * 100).round(1).astype(str) + "%"

    pie = (
        alt.Chart(filtered)
        .mark_arc()
        .encode(
            theta=alt.Theta("users:Q", title="Users (selected total)"),
            color=alt.Color("program:N", title="Program"),
            tooltip=[
                alt.Tooltip("program:N", title="Program"),
                alt.Tooltip("users:Q", title="Users"),
                alt.Tooltip("percent:Q", title="% of selected", format=".1%")
            ]
        )
    )
    labels = (
        alt.Chart(filtered)
        .mark_text(radius=110)
        .encode(theta=alt.Theta("users:Q", stack=True),
                text=alt.Text("percent_label:N"))
    )
    st.altair_chart(pie + labels, use_container_width=True)
