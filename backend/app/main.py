import json
import math
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Empty
from typing import Any, Dict, List
from urllib.parse import urlparse
from app.services.google_discovery import run_google_places_actor_stream
import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Company, LeadRequest
from app.services.apify_service import (
    enrich_companies,
    fetch_company_signals_from_serp,
    run_salesnav_search,
)
from app.services.query_splitter import split_queries
from app.services.stream_manager import (
    clear_request_rows,
    get_all_request_rows,
    get_request_rows,
    get_updates,
    pop_subscriber,
    push_update,
    register_subscriber,
    remove_subscriber,
)
from app.services.taxonomy_service import get_linkedin_taxonomy

Base.metadata.create_all(bind=engine)


def _ensure_schema():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("lead_requests")}
    if "agent_type" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lead_requests ADD COLUMN agent_type VARCHAR"))
            conn.execute(text("UPDATE lead_requests SET agent_type = 'salesnav' WHERE agent_type IS NULL"))


_ensure_schema()

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
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


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

    normalized_map = {_normalize_key(k): v for k, v in row.items()}

    for alias in aliases:
        value = normalized_map.get(_normalize_key(alias))
        value = _clean_value(value)
        if value is not None:
            return value

    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def extract_domain(url):
    try:
        return urlparse(url).netloc.lower().strip()
    except Exception:
        return None


def _fingerprint_company(item: Dict[str, Any]) -> str | None:
    fingerprint = item.get("url") or item.get("linkedinUrl") or extract_domain(item.get("website"))

    if not fingerprint:
        fingerprint = item.get("name")

    if not fingerprint:
        return None

    return str(fingerprint).strip().lower()


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
        row = _model_to_dict(company)
        raw_data = row.pop("raw_data", None) or {}

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


def _update_request_state(db: Session, request: LeadRequest, **kwargs):
    for key, value in kwargs.items():
        setattr(request, key, value)
    db.commit()
    db.refresh(request)

    push_update(
        request.id,
        {
            "type": "status",
            "request_id": request.id,
            "agent_type": request.agent_type,
            "status": request.status,
            "phase": request.phase,
            "progress": request.progress,
            "total_results": request.total_results,
        },
    )


def run_pipeline(request_id: int, filters: Dict[str, Any]):
    db = SessionLocal()

    try:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            return

        db.query(Company).filter_by(request_id=request_id).delete()
        db.commit()
        clear_request_rows(request_id)

        queries = split_queries(filters)
        if not queries:
            _update_request_state(
                db,
                request,
                status="Failed",
                phase="failed",
                progress=100,
                total_results=0,
            )
            return

        _update_request_state(db, request, status="Running", phase="searching", progress=10, total_results=0)

        max_total_results = max(50, min(_safe_int(filters.get("max_results"), 1000), 3000))
        max_workers = max(1, min(_safe_int(os.getenv("SALESNAV_MAX_WORKERS"), 4), len(queries)))
        max_results_per_query = max(30, min(200, math.ceil(max_total_results / len(queries))))

        seen_fingerprints = set()
        seen_lock = threading.Lock()
        total_lock = threading.Lock()
        stop_event = threading.Event()
        total_inserted = 0

        def worker(bucket_index: int, search_url: str) -> Dict[str, Any]:
            inserted_local = 0

            try:
                if stop_event.is_set():
                    return {"bucket": bucket_index, "inserted": 0, "error": None}

                search_results = run_salesnav_search(search_url, max_results=max_results_per_query)

                company_urls = []
                for item in search_results:
                    linkedin_url = item.get("linkedinUrl") or item.get("companyLinkedinUrl")
                    if linkedin_url and linkedin_url not in company_urls:
                        company_urls.append(linkedin_url)

                for i in range(0, len(company_urls), 25):
                    if stop_event.is_set():
                        break

                    chunk = company_urls[i : i + 25]

                    try:
                        enriched = enrich_companies(chunk)
                    except Exception as enrich_error:
                        push_update(
                            request_id,
                            {
                                "type": "warning",
                                "message": f"Company enrichment chunk failed: {str(enrich_error)}",
                                "bucket": bucket_index,
                            },
                        )
                        continue

                    for item in enriched:
                        if stop_event.is_set():
                            break

                        fingerprint = _fingerprint_company(item)
                        if not fingerprint:
                            continue

                        with seen_lock:
                            if fingerprint in seen_fingerprints:
                                continue
                            seen_fingerprints.add(fingerprint)

                        with total_lock:
                            total_inserted += 1
                            current_total = total_inserted
                            if total_inserted >= max_total_results:
                                stop_event.set()

                        payload = {
                            "type": "company",
                            "request_id": request_id,
                            "id": current_total,
                            "query": str(bucket_index + 1),
                            "company_name": item.get("name") or item.get("companyName"),
                            "company_url": item.get("url") or item.get("linkedinUrl"),
                            "industry": item.get("industry"),
                            "employees_count": str(item.get("employees")) if item.get("employees") is not None else None,
                            "total_results": current_total,
                            "raw_data": {k: _safe_jsonable(v) for k, v in item.items()},
                        }
                        push_update(request_id, payload)
                        inserted_local += 1

                return {"bucket": bucket_index, "inserted": inserted_local, "error": None}

            except Exception as error:
                return {"bucket": bucket_index, "inserted": inserted_local, "error": str(error)}

        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, idx, query) for idx, query in enumerate(queries)]

            for future in as_completed(futures):
                completed += 1
                outcome = future.result()

                progress = min(95, 10 + int((completed / len(queries)) * 80))
                request.progress = progress
                request.phase = "processing"
                request.total_results = total_inserted

                if outcome.get("error"):
                    push_update(
                        request_id,
                        {
                            "type": "warning",
                            "request_id": request_id,
                            "message": f"Bucket {outcome['bucket'] + 1} error: {outcome['error']}",
                        },
                    )

                db.commit()

                push_update(
                    request_id,
                    {
                        "type": "status",
                        "request_id": request_id,
                        "status": request.status,
                        "phase": request.phase,
                        "progress": request.progress,
                        "total_results": request.total_results,
                    },
                )

        request.total_results = total_inserted
        request.progress = 100

        if total_inserted > 0:
            request.status = "Completed"
            request.phase = "completed"
        else:
            request.status = "Failed"
            request.phase = "failed"

        db.commit()

        push_update(
            request_id,
            {
                "type": "end",
                "request_id": request_id,
                "status": request.status,
                "phase": request.phase,
                "progress": request.progress,
                "total_results": request.total_results,
            },
        )

    except Exception as exc:
        request = db.query(LeadRequest).filter_by(id=request_id).first()

        if request:
            request.status = "Failed"
            request.phase = "failed"
            request.progress = 100
            db.commit()

            push_update(
                request_id,
                {
                    "type": "error",
                    "request_id": request_id,
                    "message": str(exc),
                    "status": request.status,
                    "phase": request.phase,
                    "progress": request.progress,
                    "total_results": request.total_results,
                },
            )
    finally:
        db.close()




def run_google_discovery_pipeline(request_id: int, filters: Dict[str, Any]):
    db = SessionLocal()

    try:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            return

        # 🔹 Step 1: Start
        _update_request_state(
            db,
            request,
            status="Running",
            phase="searching",
            progress=20,
            total_results=0,
        )

        # 🔹 Step 2: Run streaming Apify
        inserted = 0
        seen = set()

        def handle_row(row):
            nonlocal inserted

            if not isinstance(row, dict):
                return

            fingerprint = (
                row.get("placeId")
                or row.get("googleMapsUrl")
                or row.get("website")
                or row.get("title")
            )

            if fingerprint:
                fingerprint = str(fingerprint).strip().lower()
                if fingerprint in seen:
                    return
                seen.add(fingerprint)

            inserted += 1

            # ✅ SAVE TO DB
            company = Company(
                request_id=request.id,
                company_name=row.get("title") or row.get("name"),
                company_url=row.get("website"),
                description=row.get("address"),
                company_id=row.get("placeId"),
                regular_company_url=row.get("googleMapsUrl"),
                industry=row.get("categoryName"),
                employees_count=row.get("reviewsCount"),
                logo_url=row.get("imageUrl"),
                raw_data={k: _safe_jsonable(v) for k, v in row.items()},
            )

            db.add(company)

            # 🔹 batch commit
            if inserted % 20 == 0:
                db.commit()

            # ✅ STREAM TO UI
            push_update(
                request.id,
                {
                    "type": "company",
                    "request_id": request.id,
                    "agent_type": request.agent_type,
                    "company_name": company.company_name,
                    "company_url": company.company_url,
                    "industry": company.industry,
                    "total_results": inserted,
                },
            )

        # 🚀 STREAMING EXECUTION
        inserted = run_google_places_actor_stream(
            filters,
            request,
            db,
            push_update,
            on_row=handle_row,   # 👈 important hook
        )

        db.commit()

        # 🔹 Step 3: Complete
        _update_request_state(
            db,
            request,
            status="Completed",
            phase="completed",
            progress=100,
            total_results=inserted,
        )

        push_update(
            request.id,
            {
                "type": "end",
                "request_id": request.id,
                "status": request.status,
                "phase": request.phase,
                "progress": request.progress,
                "total_results": inserted,
            },
        )

    except Exception as exc:
        request = db.query(LeadRequest).filter_by(id=request_id).first()

        if request:
            request.status = "Failed"
            request.phase = "failed"
            request.progress = 100
            db.commit()

            push_update(
                request_id,
                {
                    "type": "error",
                    "request_id": request_id,
                    "message": str(exc),
                },
            )

    finally:
        db.close()

def run_firmographic_enrichment_pipeline(request_id: int, filters: Dict[str, Any]):
    db = SessionLocal()

    try:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            return

        _update_request_state(
            db,
            request,
            status="Running",
            phase="enriching",
            progress=10,
            total_results=0,
        )

        db.query(Company).filter_by(request_id=request_id).delete()
        db.commit()

        urls = filters.get("linkedin_urls") or []
        if isinstance(urls, str):
            urls = [line.strip() for line in urls.splitlines() if line.strip()]

        if not isinstance(urls, list) or not urls:
            _update_request_state(
                db,
                request,
                status="Failed",
                phase="failed",
                progress=100,
                total_results=0,
            )
            return

        enriched = enrich_companies(urls)
        inserted = 0

        for row in enriched:
            if not isinstance(row, dict):
                continue

            serp_signals = fetch_company_signals_from_serp(
                company_name=row.get("name"),
                linkedin_url=row.get("linkedinUrl") or row.get("url"),
            )
            merged_row = {**row, **(serp_signals or {})}

            company = Company(
                request_id=request.id,
                company_url=merged_row.get("url"),
                company_name=merged_row.get("name"),
                description=merged_row.get("description"),
                company_id=merged_row.get("companyId") or merged_row.get("id"),
                regular_company_url=merged_row.get("linkedinUrl") or merged_row.get("url"),
                industry=merged_row.get("industry"),
                employees_count=str(merged_row.get("employees")) if merged_row.get("employees") is not None else None,
                employee_count_range=merged_row.get("employee_band_indicator"),
                logo_url=merged_row.get("logo"),
                raw_data={k: _safe_jsonable(v) for k, v in merged_row.items()},
            )
            db.add(company)
            inserted += 1
            db.flush()

            payload = _model_to_dict(company)
            payload.pop("raw_data", None)
            payload.update(
                {
                    "type": "company",
                    "request_id": request.id,
                    "agent_type": request.agent_type,
                    "total_results": inserted,
                }
            )
            push_update(request.id, payload)

            if inserted % 15 == 0:
                progress = min(95, 10 + int((inserted / max(len(urls), 1)) * 80))
                _update_request_state(
                    db,
                    request,
                    status="Running",
                    phase="enriching",
                    progress=progress,
                    total_results=inserted,
                )
        db.commit()
        _update_request_state(
            db,
            request,
            status="Completed",
            phase="completed",
            progress=100,
            total_results=inserted,
        )
        push_update(
            request.id,
            {
                "type": "end",
                "request_id": request.id,
                "agent_type": request.agent_type,
                "status": request.status,
                "phase": request.phase,
                "progress": request.progress,
                "total_results": request.total_results,
            },
        )
    except Exception as exc:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if request:
            request.status = "Failed"
            request.phase = "failed"
            request.progress = 100
            db.commit()
            push_update(
                request_id,
                {
                    "type": "error",
                    "request_id": request_id,
                    "agent_type": request.agent_type,
                    "message": str(exc),
                    "status": request.status,
                    "phase": request.phase,
                    "progress": request.progress,
                    "total_results": request.total_results,
                },
            )
    finally:
        db.close()

@app.get("/api/stream/{request_id}")
def stream(request_id: int):
    return get_updates(request_id)


@app.get("/api/stream/{request_id}/events")
def stream_events(request_id: int, request: Request):
    subscriber_id = register_subscriber(request_id)

    def event_generator():
        try:
            while True:
                event = pop_subscriber(request_id, subscriber_id, timeout=15)
                if event is None:
                    yield ": keepalive\n\n"
                    continue

                yield f"data: {json.dumps(event)}\n\n"
        except Empty:
            yield ": keepalive\n\n"
        finally:
            remove_subscriber(request_id, subscriber_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/api/run-salesnav")
def run_salesnav(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    request = LeadRequest(
        request_name=data.get("request_name") or "SalesNav Agent",
        status="Running",
        phase="starting",
        progress=5,
        total_results=0,
        agent_type="salesnav",
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)
    clear_request_rows(request.id)

    push_update(
        request.id,
        {
            "type": "status",
            "request_id": request.id,
            "agent_type": request.agent_type,
            "status": request.status,
            "phase": request.phase,
            "progress": request.progress,
            "total_results": request.total_results,
        },
    )

    background_tasks.add_task(run_pipeline, request.id, data)

    return {"request_id": request.id}


@app.get("/api/linkedin-taxonomy")
def linkedin_taxonomy():
    return get_linkedin_taxonomy()


@app.post("/api/run-google-discovery")
def run_google_discovery(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    request = LeadRequest(
        request_name=data.get("request_name") or "Google Discovery Agent",
        status="Running",
        phase="starting",
        progress=5,
        total_results=0,
        agent_type="google",
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    push_update(
        request.id,
        {
            "type": "status",
            "request_id": request.id,
            "agent_type": request.agent_type,
            "status": request.status,
            "phase": request.phase,
            "progress": request.progress,
            "total_results": request.total_results,
        },
    )

    background_tasks.add_task(run_google_discovery_pipeline, request.id, data)

    return {
        "request_id": request.id,
        "agent_type": request.agent_type,
        "status": request.status,
        "phase": request.phase,
        "message": "Google scraper queued. Processing in background.",
    }


@app.post("/api/run-firmographic-enricher")
def run_firmographic_enricher(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    request = LeadRequest(
        request_name=data.get("request_name") or "Firmographic Enricher",
        status="Running",
        phase="starting",
        progress=5,
        total_results=0,
        agent_type="enrichment",
        filters=data,
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    push_update(
        request.id,
        {
            "type": "status",
            "request_id": request.id,
            "agent_type": request.agent_type,
            "status": request.status,
            "phase": request.phase,
            "progress": request.progress,
            "total_results": request.total_results,
        },
    )

    background_tasks.add_task(run_firmographic_enrichment_pipeline, request.id, data)
    return {"request_id": request.id, "agent_type": request.agent_type}


@app.get("/api/request/{request_id}")
def get_request_status(request_id: int, db: Session = Depends(get_db)):
    request = db.query(LeadRequest).filter_by(id=request_id).first()

    if not request:
        return {"error": "request not found"}

    return {
        "request_id": request.id,
        "request_name": request.request_name,
        "agent_type": request.agent_type or "salesnav",
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

    if total > 0:
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": [_model_to_dict(row) for row in rows],
        }

    return get_request_rows(request_id, page=page, limit=limit)


@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    rows = db.query(LeadRequest).all()
    payload = []
    for row in rows:
        item = _model_to_dict(row)
        item["agent_type"] = item.get("agent_type") or "salesnav"
        payload.append(item)
    return payload


@app.get("/api/download/{request_id}")
def download_file(request_id: int, format: str = Query("csv"), db: Session = Depends(get_db)):
    companies = db.query(Company).filter_by(request_id=request_id).all()

    if companies:
        rows = _build_export_rows(companies)
    else:
        rows = get_all_request_rows(request_id)
        if not rows:
            return JSONResponse(
                status_code=404,
                content={"error": "No results found for this request_id"},
            )
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
