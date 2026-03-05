"""Streamlit dashboard for the Research Opportunity Aggregator."""
import json
import glob
import os
import logging

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


def main():
    st.title("Research Opportunity Aggregator (India)")
    st.markdown(
        "Browse the latest **Research Associate / Research Assistant / "
        "Project Associate** openings from IITs, IISERs, ISI and NITs."
    )

    data = load_data()
    if not data:
        st.warning(
            "No data found. Run the scrapers first: "
            "python -m scrapers.run_all"
        )
        return

    df = pd.DataFrame(data)
    display_cols = ["institute", "title", "position_type", "deadline", "detail_url"]
    for col in display_cols:
        if col not in df.columns:
            df[col] = ""

    st.sidebar.header("Filters")

    institutes = sorted(df["institute"].dropna().unique().tolist())
    selected_institutes = st.sidebar.multiselect(
        "Institute",
        options=institutes,
        default=[],
    )

    position_types = sorted(df["position_type"].dropna().unique().tolist())
    selected_positions = st.sidebar.multiselect(
        "Position Type",
        options=position_types,
        default=[],
    )

    keyword = st.sidebar.text_input("Keyword search")

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
        )
        filtered = filtered[mask]

    st.subheader("Results ({} openings)".format(len(filtered)))

    if filtered.empty:
        st.info("No openings match the selected filters.")
        return

    show_df = filtered[display_cols].reset_index(drop=True)
    show_df.index = show_df.index + 1

    st.dataframe(
        show_df,
        use_container_width=True,
        column_config={
            "detail_url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Stats**")
    st.sidebar.metric("Total Openings", len(df))
    st.sidebar.metric("Institutes", df["institute"].nunique())
    st.sidebar.metric("Shown", len(filtered))


if __name__ == "__main__":
    main()
