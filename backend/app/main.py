import os
import json
import time
import threading
import tempfile
from typing import Any, Dict, List
from app.services.apify_service import run_salesnav_search, enrich_companies
from app.services.query_splitter import split_queries
from app.stream_manager import push_update
from app.stream_manager import get_updates
import pandas as pd
from fastapi import FastAPI, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import LeadRequest, Company
from app.services.salesnav_builder import build_salesnav_company_search
from app.services.google_discovery import run_google_places_actor
# from app.phantom_service import (
#     extract_container_id,
#     launch_company_search,
#     get_container_status,
#     fetch_container_results,
# )

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Account Building Agents SaaS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _model_to_dict(model):
    return {
        column.name: getattr(model, column.name)
        for column in model.__table__.columns
    }


def _safe_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _clean_value(value: Any):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def _normalize_key(s: str) -> str:
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def _row_get(row: Dict[str, Any], aliases: List[str]):
    if not isinstance(row, dict):
        return None

    normalized_map = {
        _normalize_key(k): v for k, v in row.items()
    }

    for alias in aliases:
        value = normalized_map.get(_normalize_key(alias))
        value = _clean_value(value)
        if value is not None:
            return value

    return None


def _is_company_row(row: Dict[str, Any]) -> bool:
    company_url = _row_get(row, ["companyUrl", "Company Url"])
    company_name = _row_get(row, ["companyName", "Company Name"])
    company_id = _row_get(row, ["companyId", "Company Id"])
    regular_company_url = _row_get(row, ["regularCompanyUrl", "Regular Company Url"])

    # must have at least meaningful company identity
    identity_score = sum(
        1 for v in [company_url, company_name, company_id, regular_company_url] if v
    )

    if identity_score < 2:
        return False

    blob = " ".join(str(v) for v in row.values() if v is not None).lower()

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

    if any(marker in blob for marker in noise_markers):
        return False

    return True


def _normalize_company_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "company_url": _row_get(row, ["companyUrl", "Company Url"]),
        "company_name": _row_get(row, ["companyName", "Company Name"]),
        "description": _row_get(row, ["description", "Description"]),
        "company_id": _row_get(row, ["companyId", "Company Id"]),
        "regular_company_url": _row_get(row, ["regularCompanyUrl", "Regular Company Url"]),
        "industry": _row_get(row, ["industry", "Industry"]),
        "employees_count": _row_get(row, ["employeesCount", "Employees Count"]),
        "employee_count_range": _row_get(row, ["employeeCountRange", "Employee Count Range"]),
        "logo_url": _row_get(row, ["logoUrl", "Logo Url"]),
        "is_hiring": _row_get(row, ["isHiring", "Is Hiring"]),
        "query": _row_get(row, ["query", "Query"]),
        "timestamp": _row_get(row, ["timestamp", "Timestamp"]),
        "search_account_profile_id": _row_get(row, ["searchAccountProfileId", "Search Account Profile Id"]),
        "search_account_profile_name": _row_get(row, ["searchAccountProfileName", "Search Account Profile Name"]),
        "raw_data": {k: _safe_jsonable(v) for k, v in row.items()},
    }


def _normalize_google_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "company_url": _row_get(row, ["website", "url", "domain"]),
        "company_name": _row_get(row, ["title", "name", "placeName"]),
        "description": _row_get(row, ["description", "address", "categoryName"]),
        "company_id": _row_get(row, ["placeId", "cid"]),
        "regular_company_url": _row_get(row, ["googleMapsUrl", "url"]),
        "industry": _row_get(row, ["categoryName", "category", "mainCategory"]),
        "employees_count": _row_get(row, ["reviewsCount"]),
        "employee_count_range": None,
        "logo_url": _row_get(row, ["imageUrl", "thumbnailUrl"]),
        "is_hiring": None,
        "query": _row_get(row, ["searchString", "searchTerm"]),
        "timestamp": _row_get(row, ["scrapedAt", "timestamp"]),
        "search_account_profile_id": None,
        "search_account_profile_name": None,
        "raw_data": {k: _safe_jsonable(v) for k, v in row.items()},
    }


def _build_export_rows(companies: List[Company]) -> List[Dict[str, Any]]:
    rows = []

    for company in companies:
        base = _model_to_dict(company)
        raw_data = base.pop("raw_data", None) or {}

        row = {
            "id": base.get("id"),
            "request_id": base.get("request_id"),
            "company_url": base.get("company_url"),
            "company_name": base.get("company_name"),
            "description": base.get("description"),
            "company_id": base.get("company_id"),
            "regular_company_url": base.get("regular_company_url"),
            "industry": base.get("industry"),
            "employees_count": base.get("employees_count"),
            "employee_count_range": base.get("employee_count_range"),
            "logo_url": base.get("logo_url"),
            "is_hiring": base.get("is_hiring"),
            "query": base.get("query"),
            "timestamp": base.get("timestamp"),
            "search_account_profile_id": base.get("search_account_profile_id"),
            "search_account_profile_name": base.get("search_account_profile_name"),
        }

        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                raw_data = {"raw_data": raw_data}

        if isinstance(raw_data, dict):
            for k, v in raw_data.items():
                if k not in row:
                    row[k] = v

        rows.append(row)

    return rows


# @app.on_event("startup")
# def resume_pending_jobs():
#     db = SessionLocal()
#     try:
#         pending = db.query(LeadRequest).filter(LeadRequest.status == "Running").all()

#         for job in pending:
#             if not job.container_id:
#                 job.status = "Failed"
#                 job.phase = "failed"
#                 job.progress = 100
#                 db.commit()
#                 continue

#             threading.Thread(
#                 target=poll_search_and_store,
#                 args=(job.id, str(job.container_id)),
#                 daemon=True
#             ).start()
#     finally:
#         db.close()

from urllib.parse import urlparse

def extract_domain(url):
    try:
        return urlparse(url).netloc
    except:
        return None
        
def run_pipeline(request_id, filters):
    

    db = SessionLocal()
    

    try:
        request = db.query(LeadRequest).get(request_id)
        db.query(Company).filter_by(request_id=request_id).delete()
        db.commit()

        queries = split_queries(filters)

        request.phase = "searching"
        request.progress = 10
        db.commit()

        all_domains = set()

        def worker(search_url):

            local_db = SessionLocal()

            try:
                try:
                    search_results = run_salesnav_search(search_url, 200)
                except Exception as e:
                    print("Search error:", e)
                    return

                company_urls = [
                    item.get("linkedinUrl") or item.get("companyLinkedinUrl")
                    for item in search_results
                    if item.get("linkedinUrl") or item.get("companyLinkedinUrl")
                ]

                #  LIMIT RESULTS → SAVE COST
                company_urls = company_urls[:200]

                for i in range(0, len(company_urls), 50):
                
                    chunk = company_urls[i:i+50]

                    try:
                        enriched = enrich_companies(chunk)
                    except Exception as e:
                        print("Enrich error:", e)
                        continue
                    
                    for item in enriched:
                    
                        website = item.get("website")

                        fingerprint = (
                            item.get("url")
                            or item.get("linkedinUrl")
                            or extract_domain(website)
                        )

                        if not fingerprint or fingerprint in all_domains:
                            continue
                        
                        all_domains.add(fingerprint)

                        company = Company(
                            request_id=request_id,
                            company_url=item.get("url"),
                            company_name=item.get("name"),
                            description=item.get("description"),
                            industry=item.get("industry"),
                            employees_count=item.get("employees"),
                            logo_url=item.get("logo"),
                            raw_data=item
                        )

                        local_db.add(company)
                        local_db.commit()

                        push_update(request_id, {
                            "name": company.company_name,
                            "website": website
                        })

            finally:
                local_db.close()
# def poll_search_and_store(request_id: int, container_id: str):
#       db = SessionLocal()

#       try:
#                 request = db.query(LeadRequest).filter_by(id=request_id).first()
#                 if not request:
#             return

#         request.phase = "searching"
#         request.progress = 25
#         db.commit()

#         db.query(Company).filter_by(request_id=request_id).delete()
#         db.commit()

#         attempts = 0
#         max_attempts = 80

#         while attempts < max_attempts:
#             try:
#                 status_response = get_container_status(container_id)
#                 status = str(status_response.get("status", "")).strip().lower()
#             except Exception:
#                 attempts += 1
#                 time.sleep(30)
#                 continue

#             if status == "finished":
#                 try:
#                     rows = fetch_container_results(container_id)
#                 except Exception:
#                     request.status = "Failed"
#                     request.phase = "failed"
#                     request.progress = 100
#                     db.commit()
#                     return

#                 request.phase = "processing"
#                 request.progress = 70
#                 db.commit()

#                 seen = set()
#                 inserted = 0

#                 for row in rows:
#                     if not isinstance(row, dict):
#                         continue

#                     if not _is_company_row(row):
#                         continue

#                     normalized = _normalize_company_row(row)

#                     fingerprint = (
#                         normalized.get("company_id")
#                         or normalized.get("company_url")
#                         or normalized.get("regular_company_url")
#                         or normalized.get("company_name")
#                     )

#                     if fingerprint:
#                         fingerprint = str(fingerprint).strip().lower()

#                     if fingerprint and fingerprint in seen:
#                         continue

#                     company = Company(
#                         request_id=request_id,
#                         company_url=normalized.get("company_url"),
#                         company_name=normalized.get("company_name"),
#                         description=normalized.get("description"),
#                         company_id=normalized.get("company_id"),
#                         regular_company_url=normalized.get("regular_company_url"),
#                         industry=normalized.get("industry"),
#                         employees_count=normalized.get("employees_count"),
#                         employee_count_range=normalized.get("employee_count_range"),
#                         logo_url=normalized.get("logo_url"),
#                         is_hiring=normalized.get("is_hiring"),
#                         query=normalized.get("query"),
#                         timestamp=normalized.get("timestamp"),
#                         search_account_profile_id=normalized.get("search_account_profile_id"),
#                         search_account_profile_name=normalized.get("search_account_profile_name"),
#                         raw_data=normalized.get("raw_data"),
#                     )

#                     db.add(company)
#                     inserted += 1

#                     if fingerprint:
#                         seen.add(fingerprint)

#                 db.commit()

#                 request.total_results = db.query(Company).filter_by(request_id=request_id).count()

#                 if request.total_results > 0:
#                     request.status = "Completed"
#                     request.phase = "completed"
#                 else:
#                     request.status = "Failed"
#                     request.phase = "failed"

#                 request.progress = 100
#                 db.commit()
#                 return

#             if status in {"error", "failed", "aborted"}:
#                 request.status = "Failed"
#                 request.phase = "failed"
#                 request.progress = 100
#                 db.commit()
#                 return

#             attempts += 1
#             time.sleep(30)

#         request.status = "Timeout"
#         request.phase = "failed"
#         request.progress = 100
#         db.commit()

#     finally:
#         db.close()

@app.get("/api/stream/{request_id}")
def stream(request_id: int):
    return get_updates(request_id)
    
@app.post("/api/run-salesnav")
def run_salesnav(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):

    request = LeadRequest(
        request_name=data.get("request_name"),
        status="Running",
        phase="starting",
        progress=5,
        total_results=0,
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    background_tasks.add_task(run_pipeline, request.id, data)

    return {"request_id": request.id}


@app.post("/api/run-google-discovery")
def run_google_discovery(data: dict, db: Session = Depends(get_db)):
    request = LeadRequest(
        request_name=data.get("request_name") or "Google Discovery Agent",
        status="Running",
        phase="searching",
        progress=20,
        total_results=0,
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    try:
        rows = run_google_places_actor(data)

        request.phase = "processing"
        request.progress = 70
        db.commit()

        seen = set()
        inserted = 0

        for row in rows:
            if not isinstance(row, dict):
                continue

            normalized = _normalize_google_row(row)
            fingerprint = (
                normalized.get("company_id")
                or normalized.get("regular_company_url")
                or normalized.get("company_url")
                or normalized.get("company_name")
            )

            if fingerprint:
                fingerprint = str(fingerprint).strip().lower()
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)

            company = Company(
                request_id=request.id,
                company_url=normalized.get("company_url"),
                company_name=normalized.get("company_name"),
                description=normalized.get("description"),
                company_id=normalized.get("company_id"),
                regular_company_url=normalized.get("regular_company_url"),
                industry=normalized.get("industry"),
                employees_count=normalized.get("employees_count"),
                employee_count_range=normalized.get("employee_count_range"),
                logo_url=normalized.get("logo_url"),
                is_hiring=normalized.get("is_hiring"),
                query=normalized.get("query"),
                timestamp=normalized.get("timestamp"),
                search_account_profile_id=normalized.get("search_account_profile_id"),
                search_account_profile_name=normalized.get("search_account_profile_name"),
                raw_data=normalized.get("raw_data"),
            )
            db.add(company)
            inserted += 1

        db.commit()

        request.total_results = inserted
        request.status = "Completed"
        request.phase = "completed"
        request.progress = 100
        db.commit()

        return {
            "request_id": request.id,
            "total_results": inserted,
            "endpoint": "run-sync-get-dataset-items",
            "actor": "compass~crawler-google-places",
        }

    except Exception as exc:
        request.status = "Failed"
        request.phase = "failed"
        request.progress = 100
        db.commit()

        return JSONResponse(
            status_code=500,
            content={
                "request_id": request.id,
                "error": str(exc),
            },
        )


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


@app.get("/api/results/{request_id}")
def get_results(request_id: int, page: int = 1, limit: int = 50, db: Session = Depends(get_db)):
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


@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    rows = db.query(LeadRequest).all()
    return [_model_to_dict(row) for row in rows]


@app.get("/api/download/{request_id}")
def download_file(request_id: int, format: str = Query("csv"), db: Session = Depends(get_db)):
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
