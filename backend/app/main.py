import os
import json
import time
import threading
import tempfile
from typing import Any, Dict, List

import pandas as pd
from fastapi import FastAPI, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import LeadRequest, Company
from app.services.company_utils import extract_domain, calculate_confidence
from app.services.salesnav_builder import build_salesnav_company_search
from app.phantom_service import (
    clear_agent_output,
    clear_agent_cache,
    extract_container_id,
    launch_company_search,
    get_container_status,
    fetch_container_results,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Account Building Agents SaaS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# DB dependency
# -------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# Startup resume
# -------------------------------------------------

@app.on_event("startup")
def resume_pending_jobs():
    db = SessionLocal()
    try:
        pending = db.query(LeadRequest).filter(LeadRequest.status == "Running").all()

        for job in pending:
            if not job.container_id:
                job.status = "Failed"
                job.phase = "failed"
                job.progress = 100
                db.commit()
                continue

            print(f"[Startup] Resuming request_id={job.id}, container_id={job.container_id}")

            threading.Thread(
                target=poll_search_and_store,
                args=(job.id, str(job.container_id)),
                daemon=True,
            ).start()
    finally:
        db.close()


# -------------------------------------------------
# Helpers
# -------------------------------------------------

SYSTEM_FIELDS = {
    "id",
    "request_id",
    "name",
    "domain",
    "website",
    "industry",
    "headcount",
    "revenue",
    "headquarters",
    "linkedin_url",
    "confidence_score",
}


def _safe_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _model_to_dict(model) -> Dict[str, Any]:
    data = {}
    for column in model.__table__.columns:
        data[column.name] = getattr(model, column.name)
    return data


def _clean_value(value: Any) -> Any:
    if isinstance(value, str):
        v = value.strip()
        return v if v != "" else None
    return value


def _is_noise_row(item: Dict[str, Any]) -> bool:
    """
    Filters Phantom / runtime logs such as AWS SDK warnings, info lines, etc.
    """
    if not isinstance(item, dict) or not item:
        return True

    values = []
    for v in item.values():
        if isinstance(v, list):
            values.extend([str(x) for x in v if x is not None])
        elif v is not None:
            values.append(str(v))

    blob = " | ".join(values).strip().lower()

    if not blob:
        return True

    noise_markers = [
        "aws sdk for javascript",
        "maintenance mode",
        "end-of-support",
        "trace-warnings",
        "process finished successfully",
        "number of results to scrape",
        "this search has already been processed",
        "[info_]",
        "warning",
        "exit code",
    ]

    return any(marker in blob for marker in noise_markers)


def _pick_first(item: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in item:
            value = _clean_value(item.get(key))
            if value is not None:
                return value
    return None


def _normalize_company_row(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map known semantic fields if present, but do not depend on hardcoded
    export columns from Phantom. Raw row is preserved separately.
    """
    linkedin_url = _pick_first(
        item,
        [
            "companyLinkedinUrl",
            "companyUrl",
            "regularCompanyUrl",
            "linkedInCompanyUrl",
            "linkedinUrl",
        ],
    )

    website = _pick_first(
        item,
        [
            "companyWebsite",
            "website",
            "companyDomain",
            "domain",
        ],
    )

    name = _pick_first(
        item,
        [
            "companyName",
            "name",
        ],
    )

    industry = _pick_first(
        item,
        [
            "industry",
            "companyIndustry",
        ],
    )

    headcount = _pick_first(
        item,
        [
            "employeesCount",
            "employeeCount",
            "employeeCountRange",
            "headcount",
            "companySize",
        ],
    )

    revenue = _pick_first(
        item,
        [
            "revenue",
            "annualRevenue",
            "companyRevenue",
        ],
    )

    headquarters = _pick_first(
        item,
        [
            "headquarters",
            "companyHeadquarters",
            "location",
        ],
    )

    domain = extract_domain(website or linkedin_url)

    return {
        "name": name,
        "linkedin_url": linkedin_url,
        "website": website,
        "domain": domain,
        "industry": industry,
        "headcount": headcount,
        "revenue": revenue,
        "headquarters": headquarters,
        "raw_data": {k: _safe_jsonable(v) for k, v in item.items()},
    }


def _build_export_rows(companies: List[Company]) -> List[Dict[str, Any]]:
    """
    Dynamic export:
    - include fixed system columns
    - include all keys from raw_data dynamically
    - do not hardcode phantom columns
    """
    all_raw_keys = set()

    parsed_rows = []
    for c in companies:
        base = _model_to_dict(c)
        raw_data = base.get("raw_data") or {}

        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                raw_data = {"raw_data": raw_data}

        if not isinstance(raw_data, dict):
            raw_data = {"raw_data": str(raw_data)}

        all_raw_keys.update(raw_data.keys())
        parsed_rows.append((base, raw_data))

    ordered_raw_keys = sorted(all_raw_keys)

    rows = []
    for base, raw_data in parsed_rows:
        row = {}

        # system columns first
        for key in [
            "id",
            "request_id",
            "name",
            "domain",
            "website",
            "industry",
            "headcount",
            "revenue",
            "headquarters",
            "linkedin_url",
            "confidence_score",
        ]:
            if key in base:
                row[key] = base.get(key)

        # dynamic phantom/raw columns next
        for raw_key in ordered_raw_keys:
            if raw_key not in row:
                row[raw_key] = raw_data.get(raw_key)

        rows.append(row)

    return rows


# -------------------------------------------------
# Poll Phantom and store results
# -------------------------------------------------

def poll_search_and_store(request_id: int, container_id: str):
    db = SessionLocal()

    try:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            print(f"[Poll] Request not found: {request_id}")
            return

        request.phase = "searching"
        request.progress = 25
        db.commit()

        # remove previous rows for this request before storing fresh results
        db.query(Company).filter_by(request_id=request_id).delete()
        db.commit()

        attempts = 0
        max_attempts = 80

        while attempts < max_attempts:
            try:
                status_response = get_container_status(container_id)
                status = str(status_response.get("status", "")).strip().lower()
                print(f"[Poll] container_id={container_id}, status={status}")
            except Exception as e:
                print(f"[Poll] Phantom status error: {e}")
                attempts += 1
                time.sleep(30)
                continue

            if status == "finished":
                try:
                    results = fetch_container_results(container_id)
                    print(f"[Poll] fetched rows = {len(results)}")
                except Exception as e:
                    print(f"[Poll] fetch_container_results error: {e}")
                    request.status = "Failed"
                    request.phase = "failed"
                    request.progress = 100
                    db.commit()
                    return

                request.phase = "processing"
                request.progress = 70
                db.commit()

                seen_fingerprints = set()
                inserted = 0

                for item in results:
                    if not isinstance(item, dict):
                        continue

                    if _is_noise_row(item):
                        continue

                    normalized = _normalize_company_row(item)

                    normalized_linkedin = (normalized.get("linkedin_url") or "").strip().lower()
                    normalized_domain = (normalized.get("domain") or "").strip().lower()
                    normalized_name = (normalized.get("name") or "").strip().lower()

                    fingerprint = None
                    if normalized_linkedin:
                        fingerprint = f"linkedin:{normalized_linkedin}"
                    elif normalized_domain and normalized_domain != "linkedin.com":
                        fingerprint = f"domain:{normalized_domain}"
                    elif normalized_name:
                        fingerprint = f"name:{normalized_name}"

                    if fingerprint and fingerprint in seen_fingerprints:
                        continue

                    confidence = str(calculate_confidence(item))

                    company = Company(
                        request_id=request_id,
                        name=normalized.get("name"),
                        domain=normalized.get("domain"),
                        website=normalized.get("website"),
                        industry=normalized.get("industry"),
                        headcount=normalized.get("headcount"),
                        revenue=normalized.get("revenue"),
                        headquarters=normalized.get("headquarters"),
                        linkedin_url=normalized.get("linkedin_url"),
                        confidence_score=confidence,
                        raw_data=normalized.get("raw_data"),
                    )

                    db.add(company)

                    if fingerprint:
                        seen_fingerprints.add(fingerprint)

                    inserted += 1

                db.commit()

                request.total_results = db.query(Company).filter_by(request_id=request_id).count()

                if request.total_results == 0:
                    request.status = "Failed"
                    request.phase = "failed"
                else:
                    request.status = "Completed"
                    request.phase = "completed"

                request.progress = 100
                db.commit()

                print(f"[Poll] request_id={request_id} completed, inserted={inserted}")
                return

            if status in {"error", "failed", "aborted"}:
                request.status = "Failed"
                request.phase = "failed"
                request.progress = 100
                db.commit()
                return

            attempts += 1
            time.sleep(30)

        request.status = "Timeout"
        request.phase = "failed"
        request.progress = 100
        db.commit()

    except Exception as e:
        print(f"[Poll] fatal error: {e}")
        try:
            request = db.query(LeadRequest).filter_by(id=request_id).first()
            if request:
                request.status = "Failed"
                request.phase = "failed"
                request.progress = 100
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# -------------------------------------------------
# Run SalesNav
# -------------------------------------------------

@app.post("/api/run-salesnav")
def run_salesnav(
    data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    request = LeadRequest(
        request_name=data.get("request_name"),
        status="Launching",
        phase="searching",
        progress=10,
        total_results=0,
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    search_url = (
        data.get("search_url")
        or data.get("sales_nav_url")
        or build_salesnav_company_search(data)
    )

    print(f"[SalesNav] Generated URL: {search_url}")

    # optional, not relied upon
    clear_output_response = clear_agent_output()
    clear_cache_response = clear_agent_cache()

    response = launch_company_search(search_url)
    container_id = extract_container_id(response)

    if not container_id:
        request.status = "Failed"
        request.phase = "failed"
        request.progress = 100
        db.commit()
        return {
            "request_id": request.id,
            "search_url": search_url,
            "error": "Phantom launch did not return containerId",
            "phantom_response": response,
            "clear_output_response": clear_output_response,
            "clear_cache_response": clear_cache_response,
        }

    request.container_id = str(container_id)
    request.status = "Running"
    db.commit()

    background_tasks.add_task(
        poll_search_and_store,
        request.id,
        str(container_id),
    )

    return {
        "request_id": request.id,
        "search_url": search_url,
        "container_id": str(container_id),
        "clear_output_response": clear_output_response,
        "clear_cache_response": clear_cache_response,
    }


# -------------------------------------------------
# Request status
# -------------------------------------------------

@app.get("/api/request/{request_id}")
def get_request_status(request_id: int, db: Session = Depends(get_db)):
    request = db.query(LeadRequest).filter_by(id=request_id).first()

    if not request:
        return {"error": "request not found"}

    return {
        "request_id": request.id,
        "request_name": request.request_name,
        "status": request.status,
        "phase": request.phase,
        "progress": request.progress,
        "total_results": request.total_results,
        "container_id": request.container_id,
        "filters": request.filters,
    }


# -------------------------------------------------
# Paginated results
# -------------------------------------------------

@app.get("/api/results/{request_id}")
def get_results(
    request_id: int,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    offset = (page - 1) * limit

    query = db.query(Company).filter_by(request_id=request_id)
    rows = query.offset(offset).limit(limit).all()
    total = query.count()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": [_model_to_dict(row) for row in rows],
    }


# -------------------------------------------------
# All requests
# -------------------------------------------------

@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    rows = db.query(LeadRequest).all()
    return [_model_to_dict(row) for row in rows]


# -------------------------------------------------
# Download
# format = csv | xlsx | json
# -------------------------------------------------

@app.get("/api/download/{request_id}")
def download_file(
    request_id: int,
    format: str = Query("csv"),
    db: Session = Depends(get_db),
):
    companies = db.query(Company).filter_by(request_id=request_id).all()

    if not companies:
        return JSONResponse(
            status_code=404,
            content={"error": "No results found for this request_id"},
        )

    rows = _build_export_rows(companies)
    output_format = (format or "csv").strip().lower()

    if output_format == "json":
        file_path = os.path.join(tempfile.gettempdir(), f"salesnav_{request_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

        return FileResponse(
            file_path,
            filename=f"salesnav_{request_id}.json",
            media_type="application/json",
        )

    df = pd.DataFrame(rows)

    if output_format == "xlsx":
        file_path = os.path.join(tempfile.gettempdir(), f"salesnav_{request_id}.xlsx")
        df.to_excel(file_path, index=False)

        return FileResponse(
            file_path,
            filename=f"salesnav_{request_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    file_path = os.path.join(tempfile.gettempdir(), f"salesnav_{request_id}.csv")
    df.to_csv(file_path, index=False)

    return FileResponse(
        file_path,
        filename=f"salesnav_{request_id}.csv",
        media_type="text/csv",
    )
