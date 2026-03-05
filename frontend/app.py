"""Streamlit dashboard for the Research Opportunity Aggregator."""
import json
import glob
import os
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

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
    show_df.index = show_df.index + 1

    st.dataframe(
        show_df,
        use_container_width=True,
        column_config={
            "institute":      st.column_config.TextColumn("Institute"),
            "department":     st.column_config.TextColumn("Department"),
            "title":          st.column_config.TextColumn("Title"),
            "position_type":  st.column_config.TextColumn("Type"),
            "deadline":       st.column_config.TextColumn("Deadline"),
            "detail_url":     st.column_config.LinkColumn("Link", display_text="Open ↗"),
        },
        height=600,
    )

    st.sidebar.metric("Shown", len(filtered))


if __name__ == "__main__":
    main()
