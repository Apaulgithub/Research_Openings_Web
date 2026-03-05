🚀 Research Opportunity Aggregator (India)

A centralized platform to aggregate Research Associate, Research Assistant, and Project Associate openings from India's premier institutes (IITs, IISERs, ISI, NITs).

📌 Project Overview

The goal is to solve the problem of "decentralized job postings" in Indian academia. Instead of students checking 50+ different institute websites, this tool will scrape, categorize, and display them in one searchable dashboard.

🏗️ Technical Architecture

    Ingestion: Python-based scrapers (Scrapy/Selenium) targeting /recruitment or /project-vacancies pages.

    Processing: * Text extraction from HTML and PDFs (PyMuPDF).

        Entity extraction (Post Title, Salary, Deadline, Eligibility) using NLP.

    Storage: MongoDB (for raw JSON data) + PostgreSQL (for structured, searchable data).

    Frontend: Streamlit or React for the job board.

    Automation: GitHub Actions to trigger scrapers daily.

📂 Project Structure

research-aggregator/
├── scrapers/               # Individual scripts for each institute
│   ├── iit_kharagpur.py
│   ├── iiser_pune.py
│   └── utils.py            # Common cleaning functions
├── data/                   # Local cache for scraped JSON/PDFs
├── backend/                # FastAPI / Flask logic
├── frontend/               # Streamlit or React components
├── requirements.txt        # Project dependencies
└── project.md               # You are here


🛠️ Initialization Steps (For Copilot/Agents)

1. Environment Setup

    Python Version: 3.10+
    Key Libraries: beautifulsoup4, selenium, pandas, spacy, pymupdf, fastapi.

2. Scraping Strategy

For each institute, the agent should:

    Identify the "Recruitment" URL.

    Check if the table is static (use BS4) or dynamic (use Selenium).

    Extract the link to the official PDF notification.

    Parse the PDF to find the Application Deadline.

3. Target Institutes (Phase 1)
Institute	Target URL Type	Priority
IIT	Project Staff Page	High
IISER	Vacancies Page	High
ISI	Career/Project Page	High
NIT	Recruitment Page	Medium

🧠 Phase 2: Data Refining & Intelligence

Raw scraped data is often messy. You’ll need a pipeline to "understand" the text:

    Categorization: Use NLP (Spacy/NLTK) to identify if an opening is for a JRF (Junior Research Fellow), SRF, or Project Associate.

    Entity Extraction: Extract key dates (Application Deadline), Stipend amount, and Eligibility (e.g., "GATE/NET qualified").

    Deduplication: Since some positions are posted on both the main site and department pages, use FuzzyWuzzy or hashing to avoid duplicate listings.

📝 TODO List

    [ ] Initialize git repository.

    [ ] Create a base Scraper class in scrapers/utils.py.

    [ ] Write the first scraper for IIT Delhi (Project Openings).

    [ ] Setup a basic FastAPI endpoint to serve the scraped data.

    [ ] Build a simple Streamlit UI with filters for "Institute" and "Position Type".

🤖 Instructions for GitHub Copilot

    "When helping me write scrapers, prioritize robust error handling (Try-Except blocks) for network timeouts. Use Python's logging module instead of print statements. For PDF parsing, focus on extracting date-like strings to determine the application deadline."


Note: Don't ever create any unnecessary documents in the project workspace. And don't add any kind of emojis or blank spaces in the coding part also.