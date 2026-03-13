from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine, SessionLocal
from .models import LeadRequest, Company

from app.services.company_utils import extract_domain, calculate_confidence
from app.services.salesnav_builder import build_salesnav_company_search

from app.phantom_service import (
    launch_company_search,
    get_container_status,
    fetch_container_results
)

import time
import pandas as pd

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

    pending = db.query(LeadRequest).filter(
        LeadRequest.status == "Running"
    ).all()

    for job in pending:

        print("Resuming job:", job.id)

        poll_search_and_store(job.id, job.container_id)

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
        db.commit()

        attempts = 0

        while attempts < 40:

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

                for item in results:

                    domain = extract_domain(item.get("website"))
                    confidence = calculate_confidence(item)

                    existing = db.query(Company).filter_by(
                        request_id=request_id,
                        domain=domain
                    ).first()

                    if existing:
                        continue

                    company = Company(
                        request_id=request_id,
                        name=item.get("companyName"),
                        linkedin_url=item.get("linkedInCompanyUrl") or item.get("linkedInProfileUrl"),
                        website=item.get("website"),
                        domain=domain,
                        industry=item.get("industry"),
                        headcount=item.get("employeeCountRange"),
                        revenue=item.get("revenue"),
                        headquarters=item.get("location"),
                        confidence_score=confidence
                    )

                    db.add(company)

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

            elif status == "error":

                request.status = "Failed"
                db.commit()
                return

            time.sleep(30)
            attempts += 1

        request.status = "Timeout"
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

    response = launch_company_search(search_url, data)

    container_id = (
        response.get("containerId")
        or response.get("id")
        or (response.get("data", {}) or {}).get("containerId")
    )

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

    results = db.query(Company).filter_by(
        request_id=request_id
    ).offset(offset).limit(limit).all()

    total = db.query(Company).filter_by(
        request_id=request_id
    ).count()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": results
    }


# -------------------------------------------------
# List requests
# -------------------------------------------------

@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    return db.query(LeadRequest).all()


# -------------------------------------------------
# CSV Export
# -------------------------------------------------

@app.get("/api/download/{request_id}")
def download_csv(request_id: int, db: Session = Depends(get_db)):

    companies = db.query(Company).filter_by(request_id=request_id).all()

    data = [{
        "Company": c.name,
        "Domain": c.domain,
        "Industry": c.industry,
        "Employees": c.headcount,
        "Revenue": c.revenue,
        "Location": c.headquarters,
        "Website": c.website,
        "LinkedIn": c.linkedin_url,
        "Confidence": c.confidence_score
    } for c in companies]

    df = pd.DataFrame(data)

    file_path = f"/tmp/request_{request_id}.csv"

    df.to_csv(file_path, index=False)

    return FileResponse(
        file_path,
        filename=f"salesnav_{request_id}.csv",
        media_type="text/csv"
    )
