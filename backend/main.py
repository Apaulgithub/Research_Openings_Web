"""FastAPI backend for the Research Opportunity Aggregator."""
import json
import glob
import logging
import os
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.models import Opening, OpeningResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

app = FastAPI(
    title="Research Opportunity Aggregator",
    description=(
        "API to search and filter Research Associate, "
        "Research Assistant and Project Associate openings "
        "across IITs, IISERs, ISI and NITs."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_openings():
    """Load the most recent merged JSON from the data directory."""
    pattern = os.path.join(DATA_DIR, "all_openings_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
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

    try:
        with open(files[0], "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, IOError) as exc:
        logger.error("Failed to load %s: %s", files[0], exc)
        return []


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Research Opportunity Aggregator"}


@app.get("/api/openings", response_model=OpeningResponse)
def list_openings(
    institute: Optional[str] = Query(None, description="Filter by institute name (partial match)."),
    network: Optional[str] = Query(None, description="Filter by network (IIT, NIT, IIIT, IISER, ISI)."),
    position_type: Optional[str] = Query(None, description="Filter by position type (jrf, srf, project_associate, etc.)."),
    keyword: Optional[str] = Query(None, description="Search keyword in title or raw text."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(20, ge=1, le=100, description="Results per page."),
):
    """Return a paginated, filterable list of research openings."""
    openings = _load_openings()

    if institute:
        institute_lower = institute.lower()
        openings = [
            o for o in openings if institute_lower in o.get("institute", "").lower()
        ]

    if network:
        net_lower = network.lower()
        openings = [
            o for o in openings if o.get("network", "").lower() == net_lower
        ]

    if position_type:
        pos_lower = position_type.lower()
        openings = [
            o for o in openings if o.get("position_type", "").lower() == pos_lower
        ]

    if keyword:
        kw_lower = keyword.lower()
        openings = [
            o for o in openings
            if kw_lower in o.get("title", "").lower()
            or kw_lower in o.get("raw_text", "").lower()
        ]

    total = len(openings)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = openings[start:end]

    return OpeningResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[Opening(**item) for item in page_results],
    )


@app.get("/api/institutes")
def list_institutes():
    """Return the distinct list of institutes present in the data."""
    openings = _load_openings()
    institutes = sorted({o.get("institute", "") for o in openings if o.get("institute")})
    return {"institutes": institutes}


@app.get("/api/position-types")
def list_position_types():
    """Return the distinct position types found in the data."""
    openings = _load_openings()
    types = sorted({o.get("position_type", "") for o in openings if o.get("position_type")})
    return {"position_types": types}


@app.get("/api/networks")
def list_networks():
    """Return the distinct network types found in the data (IIT, NIT, IIIT, IISER, ISI)."""
    openings = _load_openings()
    networks = sorted({o.get("network", "") for o in openings if o.get("network")})
    return {"networks": networks}
