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

# ── Fallback URLs per institute (from support/URLs.md + dedicated scrapers) ──
# Used when a scraped record has no detail_url of its own.
INSTITUTE_FALLBACK_URL = {
    # IITs – dedicated scrapers
    "IIT Delhi":         "https://ird.iitd.ac.in/current-openings",
    "IIT Madras":        "https://icsrstaff.iitm.ac.in/careers/current_openings.php",
    "IIT Bombay":        "https://rnd.iitb.ac.in/jobs",
    "IIT Kharagpur":     "https://erp.iitkgp.ac.in/SRICStaffRecruitment/Advertise.jsp",
    "IIT Kanpur":        "https://www.iitk.ac.in/dord/project-vacancies",
    # IITs – generic scraper
    "IIT Roorkee":       "https://iitr.ac.in/Careers/Project%20Jobs.html",
    "IIT Guwahati":      "https://iitg.ac.in/rndproj/recruitment/",
    "IIT Hyderabad":     "https://iith.ac.in/careers/",
    "IIT Jodhpur":       "https://erponline.iitj.ac.in/RnDOutside/projectTemporaryAppointment.htm",
    "IIT Indore":        "https://www.iiti.ac.in/recruitments/project-positions",
    "IIT BHU Varanasi":  "https://iitbhu.ac.in/dean/dord/recruitment",
    "IIT ISM Dhanbad":   "https://people.iitism.ac.in/~research/",
    "IIT Bhubaneswar":   "https://www.iitbbs.ac.in/index.php/home/jobs/research-jobs/",
    "IIT Gandhinagar":   "https://iitgn.ac.in/careers/staff",
    "IIT Patna":         "https://www.iitp.ac.in/?option=com_content&view=article&id=1758:notice-board-list",
    "IIT Mandi":         "https://www.iitmandi.ac.in/recruitments/project",
    "IIT Tirupati":      "https://www.iittp.ac.in/Project_Positions",
    "IIT Palakkad":      "https://iitpkd.ac.in/resstaffrect",
    "IIT Bhilai":        "https://www.iitbhilai.ac.in/index.php?pid=rnd_staff_rec",
    "IIT Goa":           "https://iitgoa.ac.in/project-position/",
    "IIT Jammu":         "https://iitjammu.ac.in/postlist/Jobs",
    "IIT Dharwad":       "https://www.iitdh.ac.in/other-recruitments",
    # NITs
    "NIT Trichy":        "https://www.nitt.edu/other/jobs",
    "NIT Surathkal":     "https://www.nitk.ac.in/announcements",
    "NIT Rourkela":      "https://www.nitrkl.ac.in/Home/FacultyStaff/SRICCECareerNotices",
    "NIT Durgapur":      "https://nitdgp.ac.in/p/careers",
    "NIT Warangal":      "https://nitw.ac.in/staffrecruit",
    "NIT Calicut":       "https://nitc.ac.in/contract-adhoc-recruitment-project-staff",
    "NIT Hamirpur":      "https://nith.ac.in/advertisement-recruitments",
    "NIT Kurukshetra":   "https://nitkkr.ac.in/jobs-nit-kkr/",
    "NIT Jamshedpur":    "https://www.nitjsr.ac.in/Recruitments",
    "NIT Silchar":       "https://www.nits.ac.in/recruitment-view-all",
    "MNNIT Allahabad":   "https://www.mnnit.ac.in/index.php/project-position",
    # IIITs
    "IIIT Allahabad":    "https://www.iiita.ac.in/announcements.php",
    "IIITM Gwalior":     "https://www.iiitm.ac.in/index.php/en/careers",
    "IIITDM Jabalpur":   "https://www.iiitdmj.ac.in/pv.php",
    "IIITDM Kancheepuram": "https://www.iiitdm.ac.in/recruitment/project-positions",
    "IIITDM Kurnool":    "https://iiitk.ac.in/Project-Recruitments/page",
    "IIIT Sri City":     "https://iiits.ac.in/ticker/upcoming-events-announcements/",
    "IIIT Guwahati":     "https://www.iiitg.ac.in/iitg_reqr?ct=RzNJNURKa005enFYa3RJWWtvM2cvQT09",
    "IIIT Kalyani":      "https://iiitkalyani.ac.in/career",
    "IIIT Lucknow":      "https://iiitl.ac.in/index.php/project-vacancy/",
    "IIIT Dharwad":      "https://iiitdwd.ac.in/careers/",
    "IIIT Manipur":      "https://iiitmanipur.ac.in/pages/recruitment/recruit.php",
    "IIIT Nagpur":       "https://www.iiitn.ac.in/recruitments",
    "IIIT Pune":         "https://iiitp.ac.in/careers",
    "IIIT Ranchi":       "https://iiitranchi.ac.in/Recruitments.aspx",
    "IIIT Surat":        "https://iiitsurat.ac.in/career",
    "IIIT Bhopal":       "https://iiitbhopal.ac.in/",
    "IIIT Bhagalpur":    "https://www.iiitbh.ac.in/recruitment-2024",
    "IIIT Agartala":     "https://iiitagartala.ac.in/recruitment.html",
    "IIIT Naya Raipur":  "https://www.iiitnr.ac.in/employment-data",
    "IIIT Una":          "https://iiitu.ac.in/recruitment",
    "IIIT Tiruchirappalli": "https://iiitt.ac.in/",
    "IIIT Vadodara":     "https://iiitvadodara.ac.in/staff_positions.php",
    "IIIT Kota":         "https://iiitkota.ac.in/recruitment",
    "IIIT Sonepat":      "https://iiitsonepat.ac.in/",
    "IIIT Raichur":      "https://iiitr.ac.in/careers",
    "IIIT Kottayam":     "https://www.iiitkottayam.ac.in/#!career",
    # IISERs
    "IISER Pune":        "https://www.iiserpune.ac.in/opportunities/openings",
    "IISER Kolkata":     "https://www.iiserkol.ac.in/old/en/announcements/advertisement/",
    "IISER Mohali":      "https://www.iisermohali.ac.in/project-positions",
    "IISER Bhopal":      "https://iiserb.ac.in/join_iiserb",
    "IISER TVM":         "https://www.iisertvm.ac.in/openings",
    "IISER Tirupati":    "https://www.iisertirupati.ac.in/jobs/",
    "IISER Berhampur":   "https://www.iiserbpr.ac.in/opportunity/contractual",
    # ISIs
    "ISI Kolkata":       "https://www.isical.ac.in/public/jobs",
    "ISI Delhi":         "https://www.isid.ac.in/~statmath/index.php?module=Academics",
    "ISI Bangalore":     "https://www.isibang.ac.in/~eau/jobopportunities.htm",
    "ISI Chennai":       "https://isic.isichennai.res.in/assets/Oth/Jobs/",
    "ISI Tezpur":        "https://www.isine.ac.in/careers.php",
}

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
    for col in ["institute", "title", "position_type", "deadline", "detail_url", "raw_text"]:
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

    display_cols = ["institute", "title", "position_type", "deadline", "detail_url"]
    show_df = filtered[display_cols].reset_index(drop=True)

    # ── Render via components.html so target=_blank links actually open ───────
    def _make_link(url, institute):
        """Return a link cell. Falls back to the institute's portal URL if blank."""
        clean_url = str(url).strip() if url else ""
        if not clean_url or not clean_url.startswith("http"):
            clean_url = INSTITUTE_FALLBACK_URL.get(str(institute), "")
            if clean_url:
                return f'<a href="{clean_url}" target="_blank" rel="noopener noreferrer" class="portal">Portal ↗</a>'
            return "—"
        return f'<a href="{clean_url}" target="_blank" rel="noopener noreferrer">Open ↗</a>'

    html_rows = ""
    for i, row in enumerate(show_df.itertuples(index=False), start=1):
        link_cell = _make_link(row.detail_url, row.institute)
        title_escaped = str(row.title).replace("<", "&lt;").replace(">", "&gt;")
        html_rows += (
            f"<tr>"
            f"<td class='num'>{i}</td>"
            f"<td class='inst'>{row.institute}</td>"
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
  td.inst {{ width: 150px; font-weight: 600; color: #1f4e79; }}
  td.title{{ width: 380px; }}
  td.type {{ width: 120px; }}
  td.dl   {{ width: 110px; white-space: nowrap; }}
  td.link {{ width: 70px; text-align: center; }}
  a {{ color: #1a73e8; font-weight: 700; text-decoration: none; }}
  a:hover {{ text-decoration: underline; color: #0d47a1; }}
  a.portal {{ color: #6a1e9e; }}
</style>
</head>
<body>
<div class="wrap">
<table>
  <thead>
    <tr>
      <th>#</th><th>Institute</th>
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
