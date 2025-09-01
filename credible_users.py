import requests, pandas as pd, streamlit as st, streamlit.components.v1 as components, altair as alt

st.set_page_config(page_title="Airtable Embed + Program Users", layout="wide")
st.title("Airtable Embed + Program Users")

PAT       = st.secrets.get("AIRTABLE_PAT")
BASE_ID   = st.secrets.get("AIRTABLE_BASE")
EMBED_URL = st.secrets.get("AIRTABLE_EMBED_URL")
VIEW_NAME = st.secrets.get("AIRTABLE_VIEW")  # e.g., "Credible Users Program Report"
if not all([PAT, BASE_ID, EMBED_URL, VIEW_NAME]):
    st.error("Add AIRTABLE_PAT, AIRTABLE_BASE, AIRTABLE_EMBED_URL, and AIRTABLE_VIEW to secrets.")
    st.stop()

left, right = st.columns([2, 1], gap="large")
with left:
    st.subheader("Embedded Airtable View")
    components.html(f'<iframe src="{EMBED_URL}" width="100%" height="700" style="border:1px solid #ddd;"></iframe>', height=720)
    st.caption("Pie chart uses the exact same Airtable view.")

# Hard-code the field names that appear in your screenshot
PROGRAM_FIELD = "Program Name"
USERS_FIELD   = "Credible Users"

@st.cache_data(show_spinner=True)
def get_table_for_view(pat: str, base_id: str, view_name: str) -> str | None:
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    r = requests.get(url, headers={"Authorization": f"Bearer {pat}"}, timeout=30)
    r.raise_for_status()
    for t in r.json().get("tables", []):
        for v in t.get("views", []):
            if v.get("name") == view_name:
                return t["name"]
    return None

table_name = get_table_for_view(PAT, BASE_ID, VIEW_NAME)
if not table_name:
    st.error(f"Couldn't find a view named '{VIEW_NAME}' in base {BASE_ID}. Double-check the exact view name.")
    st.stop()

@st.cache_data(show_spinner=True)
def fetch_view_records(pat: str, base_id: str, table: str, view_name: str) -> pd.DataFrame:
    url = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(table)}"
    headers = {"Authorization": f"Bearer {pat}"}
    params = {"view": view_name}
    out = []
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        out.extend(data.get("records", []))
        if "offset" in data:
            params["offset"] = data["offset"]
        else:
            break
    return pd.json_normalize([r.get("fields", {}) for r in out])

df = fetch_view_records(PAT, BASE_ID, table_name, VIEW_NAME)

st.subheader(f"Credible Users by Program — View: {VIEW_NAME}")
if df.empty:
    st.info("This view returned no rows.")
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

    total = chart_df["users"].sum()
    if total == 0:
        st.info("Total users in this view are zero.")
    else:
        chart_df["percent"] = chart_df["users"] / total
        chart_df["percent_label"] = (chart_df["percent"] * 100).round(1).astype(str) + "%"

        pie = (
            alt.Chart(chart_df)
            .mark_arc()
            .encode(
                theta=alt.Theta("users:Q", title="Users (view total)"),
                color=alt.Color("program:N", title="Program"),
                tooltip=[
                    alt.Tooltip("program:N", title="Program"),
                    alt.Tooltip("users:Q", title="Users"),
                    alt.Tooltip("percent:Q", title="% of view", format=".1%")
                ]
            )
        )
        labels = (
            alt.Chart(chart_df)
            .mark_text(radius=110)
            .encode(theta=alt.Theta("users:Q", stack=True),
                    text=alt.Text("percent_label:N"))
        )
        st.altair_chart(pie + labels, use_container_width=True)
