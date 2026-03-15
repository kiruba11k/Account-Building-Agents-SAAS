from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
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
    fetch_container_results
)

import time
import pandas as pd
import threading

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------------------------------
# Resume unfinished jobs (Render sleep protection)
# -------------------------------------------------

@app.on_event("startup")
def resume_pending_jobs():
    db = SessionLocal()
    try:
        pending = db.query(LeadRequest).filter(
            LeadRequest.status == "Running"
        ).all()

        for job in pending:
            print("Resuming job:", job.id)

            threading.Thread(
                target=poll_search_and_store,
                args=(job.id, job.container_id),
                daemon=True
            ).start()
    finally:
        db.close()


# -------------------------------------------------
# Database dependency
# -------------------------------------------------

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


# -------------------------------------------------
# Poll Phantom and store results
# -------------------------------------------------

def poll_search_and_store(request_id, container_id):

    db = SessionLocal()

    try:

        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            print("Request not found:", request_id)
            return

        request.phase = "searching"
        request.progress = 25

        # Defensive cleanup in case the job is resumed/restarted.
        db.query(Company).filter_by(request_id=request_id).delete()

        db.commit()

        attempts = 0

        while attempts < 80:

            try:
                status_response = get_container_status(container_id)
                status = status_response.get("status")
            except Exception as e:
                print("Phantom status error:", e)
                time.sleep(30)
                attempts += 1
                continue

            if status == "finished":

                results = fetch_container_results(container_id)

                request.phase = "processing"
                request.progress = 70
                db.commit()

                seen_fingerprints = set()

                for item in results:

                    linkedin_url = (
                        item.get("companyLinkedinUrl")
                        or item.get("companyUrl")
                        or item.get("regularCompanyUrl")
                        or item.get("linkedInCompanyUrl")
                        or item.get("linkedinUrl")
                    )

                    website = (
                        item.get("companyWebsite")
                        or item.get("website")
                        or item.get("companyDomain")
                    )

                    domain = extract_domain(website)

                    normalized_linkedin = (linkedin_url or "").strip().lower()
                    normalized_domain = (domain or "").strip().lower()
                    normalized_name = (
                        item.get("companyName")
                        or item.get("name")
                        or ""
                    ).strip().lower()

                    fingerprint = None

                    if normalized_linkedin:
                        fingerprint = f"linkedin:{normalized_linkedin}"
                    elif normalized_domain and normalized_domain != "linkedin.com":
                        fingerprint = f"domain:{normalized_domain}"
                    elif normalized_name:
                        fingerprint = f"name:{normalized_name}"

                    if fingerprint and fingerprint in seen_fingerprints:
                        continue

                    confidence = calculate_confidence(item)

                    company = Company(

                        request_id=request_id,

                        name=name,

                        linkedin_url=linkedin_url,

                        website=website,

                        domain=domain,

                        industry=industry,

                        headcount=headcount,

                        revenue=revenue,

                        headquarters=headquarters,

                        confidence_score=confidence
                    )

                    db.add(company)

                    if fingerprint:
                        seen_fingerprints.add(fingerprint)

                db.commit()

                request.total_results = db.query(Company).filter_by(
                    request_id=request_id
                ).count()

                if request.total_results == 0:
                    request.status = "Failed"
                    request.phase = "failed"
                else:
                    request.status = "Completed"
                    request.phase = "completed"

                request.progress = 100
                db.commit()
                return

            if status == "error":
                request.status = "Failed"
                request.phase = "failed"
                request.progress = 100
                db.commit()
                return

            time.sleep(30)
            attempts += 1

        request.status = "Timeout"
        request.phase = "failed"
        request.progress = 100
        db.commit()

    finally:
        db.close()


# -------------------------------------------------
# Run SalesNav pipeline
# -------------------------------------------------

@app.post("/api/run-salesnav")
def run_salesnav(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):

    request = LeadRequest(
        request_name=data.get("request_name"),
        status="Launching",
        phase="searching",
        progress=10,
        filters=data
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    # Allow direct Sales Navigator URLs for fully pre-configured Phantom agents.
    search_url = (
        data.get("search_url")
        or data.get("sales_nav_url")
        or build_salesnav_company_search(data)
    )

    print(f"[SalesNav] Generated URL: {search_url}")

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
        str(container_id)
    )

    return {
        "request_id": request.id,
        "search_url": search_url
    }


# -------------------------------------------------
# Request status API
# -------------------------------------------------

@app.get("/api/request/{request_id}")
def get_request_status(request_id: int, db: Session = Depends(get_db)):

    request = db.query(LeadRequest).filter_by(id=request_id).first()

    if not request:
        return {"error": "request not found"}

    return {
        "status": request.status,
        "phase": request.phase,
        "progress": request.progress,
        "total_results": request.total_results
    }


# -------------------------------------------------
# Pagination results API
# -------------------------------------------------

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
        "results": [_model_to_dict(row) for row in rows]
    }


# -------------------------------------------------
# List requests
# -------------------------------------------------

@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    rows = db.query(LeadRequest).all()
    return [_model_to_dict(row) for row in rows]


# -------------------------------------------------
# CSV Export
# -------------------------------------------------

@app.get("/api/download/{request_id}")
def download_csv(request_id: int, format: str = "csv", db: Session = Depends(get_db)):

    companies = db.query(Company).filter_by(request_id=request_id).all()

    data = [_model_to_dict(c) for c in companies]

    df = pd.DataFrame(data)

    output_format = (format or "csv").strip().lower()

    if output_format == "xlsx":
        file_path = f"/tmp/request_{request_id}.xlsx"
        df.to_excel(file_path, index=False)
        return FileResponse(
            file_path,
            filename=f"salesnav_{request_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    file_path = f"/tmp/request_{request_id}.csv"

    df.to_csv(file_path, index=False)

    return FileResponse(
        file_path,
        filename=f"salesnav_{request_id}.csv",
        media_type="text/csv"
    )
