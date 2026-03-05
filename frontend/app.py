"""Streamlit dashboard for the Research Opportunity Aggregator."""
import json
import glob
import os
import logging
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

st.set_page_config(
    page_title="Research Opportunity Aggregator",
    page_icon=None,
    layout="wide",
)


@st.cache_data(ttl=300)
def load_data():
    """Load openings from the most recent merged JSON."""
    pattern = os.path.join(DATA_DIR, "all_openings_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        try:
            with open(files[0], "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, IOError) as exc:
            logger.error("Failed to load %s: %s", files[0], exc)

    individual = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    all_data = []
    for fpath in individual:
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                all_data.extend(data)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Skipping %s: %s", fpath, exc)
    return all_data


def _parse_deadline_for_sort(deadline_str):
    """Convert a deadline string to a sortable date. Returns pd.NaT if unparseable."""
    if not deadline_str or not deadline_str.strip():
        return pd.NaT
    for fmt in (
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d %b. %Y",
    ):
        try:
            return pd.Timestamp(datetime.strptime(deadline_str.strip(), fmt))
        except ValueError:
            continue
    # Try pandas flexible parser as last resort
    try:
        return pd.Timestamp(deadline_str.strip())
    except Exception:
        return pd.NaT


def main():
    st.title("Research Opportunity Aggregator (India)")
    st.markdown(
        "Browse the latest **Research Associate / Research Assistant / "
        "Project Associate** openings from IITs, IISERs, ISI, NITs and IIITs."
    )

    data = load_data()
    if not data:
        st.warning(
            "No data found. Run the scrapers first: "
            "python -m scrapers.run_all"
        )
        return

    df = pd.DataFrame(data)

    # Ensure all expected columns exist
    for col in ["institute", "department", "title", "position_type", "deadline", "detail_url", "raw_text"]:
        if col not in df.columns:
            df[col] = ""

    # Build a parsed-date column for sorting (hidden from display)
    df["_deadline_dt"] = df["deadline"].apply(_parse_deadline_for_sort)

    # ── Sidebar filters ──────────────────────────────────────────────────────
    st.sidebar.header("Filters")

    institutes = sorted(df["institute"].dropna().unique().tolist())
    selected_institutes = st.sidebar.multiselect("Institute", options=institutes, default=[])

    position_types = sorted(df["position_type"].dropna().unique().tolist())
    selected_positions = st.sidebar.multiselect("Position Type", options=position_types, default=[])

    keyword = st.sidebar.text_input("Keyword search")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Stats**")
    st.sidebar.metric("Total Openings", len(df))
    st.sidebar.metric("Institutes", df["institute"].nunique())
    # will be updated after filtering

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = df.copy()

    if selected_institutes:
        filtered = filtered[filtered["institute"].isin(selected_institutes)]

    if selected_positions:
        filtered = filtered[filtered["position_type"].isin(selected_positions)]

    if keyword:
        kw_lower = keyword.lower()
        mask = (
            filtered["title"].str.lower().str.contains(kw_lower, na=False)
            | filtered["raw_text"].str.lower().str.contains(kw_lower, na=False)
            | filtered["department"].str.lower().str.contains(kw_lower, na=False)
        )
        filtered = filtered[mask]

    # ── Sorting controls ──────────────────────────────────────────────────────
    st.subheader("Results ({} openings)".format(len(filtered)))

    col1, col2 = st.columns([2, 1])
    with col1:
        sort_by = st.selectbox(
            "Sort by",
            options=["Deadline (soonest first)", "Deadline (latest first)", "Institute (A→Z)", "Institute (Z→A)", "Position Type"],
            index=0,
        )
    with col2:
        hide_no_deadline = st.checkbox("Hide entries with no deadline", value=False)

    if hide_no_deadline:
        filtered = filtered[filtered["_deadline_dt"].notna()]

    if sort_by == "Deadline (soonest first)":
        # Put NaT (no deadline) at the end
        filtered = filtered.sort_values("_deadline_dt", ascending=True, na_position="last")
    elif sort_by == "Deadline (latest first)":
        filtered = filtered.sort_values("_deadline_dt", ascending=False, na_position="last")
    elif sort_by == "Institute (A→Z)":
        filtered = filtered.sort_values("institute", ascending=True)
    elif sort_by == "Institute (Z→A)":
        filtered = filtered.sort_values("institute", ascending=False)
    elif sort_by == "Position Type":
        filtered = filtered.sort_values("position_type", ascending=True)

    if filtered.empty:
        st.info("No openings match the selected filters.")
        return

    display_cols = ["institute", "department", "title", "position_type", "deadline", "detail_url"]
    show_df = filtered[display_cols].reset_index(drop=True)

    # ── Render via components.html so target=_blank links actually open ───────
    # st.markdown strips/intercepts anchor clicks at the React layer;
    # components.html() renders in a fully isolated iframe that respects
    # standard browser link behaviour.
    def _make_link(url):
        if url and str(url).startswith("http"):
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">Open ↗</a>'
        return "—"

    html_rows = ""
    for i, row in enumerate(show_df.itertuples(index=False), start=1):
        link_cell = _make_link(row.detail_url)
        dept = str(row.department) if row.department else ""
        title_escaped = str(row.title).replace("<", "&lt;").replace(">", "&gt;")
        html_rows += (
            f"<tr>"
            f"<td class='num'>{i}</td>"
            f"<td class='inst'>{row.institute}</td>"
            f"<td class='dept'>{dept}</td>"
            f"<td class='title'>{title_escaped}</td>"
            f"<td class='type'>{row.position_type}</td>"
            f"<td class='dl'>{row.deadline or '—'}</td>"
            f"<td class='link'>{link_cell}</td>"
            f"</tr>\n"
        )

    # Estimate height: 38px per row + 80px header/padding, cap at 700px
    table_height = min(80 + len(show_df) * 38, 700)

    html_page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          font-size: 13px; background: #fff; }}
  .wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
      background: #1f4e79; color: #fff;
      padding: 8px 10px; text-align: left;
      position: sticky; top: 0; z-index: 2;
      white-space: nowrap;
  }}
  tbody td {{ padding: 6px 10px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  tbody tr:nth-child(even) {{ background: #f5f8ff; }}
  tbody tr:hover {{ background: #dde8ff; }}
  td.num  {{ width: 40px; color: #888; text-align: right; }}
  td.inst {{ width: 130px; font-weight: 600; color: #1f4e79; }}
  td.dept {{ width: 160px; font-size: 12px; color: #555; }}
  td.title{{ width: 280px; }}
  td.type {{ width: 110px; }}
  td.dl   {{ width: 100px; white-space: nowrap; }}
  td.link {{ width: 70px; text-align: center; }}
  a {{ color: #1a73e8; font-weight: 700; text-decoration: none; }}
  a:hover {{ text-decoration: underline; color: #0d47a1; }}
</style>
</head>
<body>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>#</th><th>Institute</th><th>Department</th>
      <th>Title</th><th>Type</th><th>Deadline</th><th>Link</th>
    </tr>
  </thead>
  <tbody>
{html_rows}
  </tbody>
</table>
</div>
</body>
</html>"""

    components.html(html_page, height=table_height, scrolling=True)

    st.sidebar.metric("Shown", len(filtered))


if __name__ == "__main__":
    main()
