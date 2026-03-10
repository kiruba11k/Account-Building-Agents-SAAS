from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import LeadRequest, Company

from app.services.company_utils import extract_domain, calculate_confidence
from app.services.salesnav_builder import build_salesnav_company_search

from app.phantom_service import (
    launch_company_search,
    launch_company_scraper,
    get_container_status,
    fetch_container_output
)

import time
import pandas as pd

Base.metadata.create_all(bind=engine)

app = FastAPI()

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

        if job.phase == "searching":
            poll_search_and_scrape(job.id, job.container_id)

        elif job.phase == "scraping":
            poll_scraper_and_store(job.id, job.container_id)

    db.close()


# -------------------------------------------------
# Extract LinkedIn company URLs
# -------------------------------------------------

def extract_company_urls(results):

    urls = []

    for item in results:
        if item.get("linkedInCompanyUrl"):
            urls.append(item["linkedInCompanyUrl"])

    return urls


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
# Poll Search Phantom
# -------------------------------------------------

def poll_search_and_scrape(request_id, container_id):

    db = SessionLocal()

    try:

        request = db.query(LeadRequest).filter_by(id=request_id).first()

        request.phase = "searching"
        request.progress = 25
        db.commit()

        attempts = 0

        while attempts < 40:

            status_response = get_container_status(container_id)
            status = status_response.get("status")

            if status == "finished":

                output = fetch_container_output(container_id)
                search_results = output.get("data", [])

                company_urls = extract_company_urls(search_results)

                request.phase = "scraping"
                request.progress = 60
                db.commit()

                if not company_urls:

                    request.status = "Completed"
                    request.total_results = 0
                    request.progress = 100
                    db.commit()

                    return

                print("Found company URLs:", len(company_urls))

                scraper_response = launch_company_scraper(company_urls)

                scraper_container = scraper_response.get("containerId")

                request.container_id = scraper_container
                request.phase = "scraping"
                db.commit()

                poll_scraper_and_store(request_id, scraper_container)

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
# Poll Scraper Phantom
# -------------------------------------------------

def poll_scraper_and_store(request_id, container_id):

    db = SessionLocal()

    try:

        attempts = 0

        while attempts < 40:

            status_response = get_container_status(container_id)
            status = status_response.get("status")

            if status == "finished":

                output = fetch_container_output(container_id)
                results = output.get("data", [])

                request = db.query(LeadRequest).filter_by(id=request_id).first()

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
                        name=item.get("name"),
                        linkedin_url=item.get("linkedInCompanyUrl"),
                        website=item.get("website"),
                        domain=domain,
                        industry=item.get("industry"),
                        headcount=item.get("employeeCountRange"),
                        revenue=item.get("revenue"),
                        headquarters=item.get("location"),
                        confidence_score=confidence
                    )

                    db.add(company)

                request.status = "Completed"
                request.phase = "completed"
                request.progress = 100

                request.total_results = db.query(Company).filter_by(
                    request_id=request_id
                ).count()

                db.commit()

                return

            elif status == "error":

                request = db.query(LeadRequest).filter_by(id=request_id).first()
                request.status = "Failed"
                db.commit()

                return

            time.sleep(30)
            attempts += 1

        request = db.query(LeadRequest).filter_by(id=request_id).first()
        request.status = "Timeout"
        db.commit()

    finally:
        db.close()


# -------------------------------------------------
# Run SalesNav Pipeline
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

    search_url = build_salesnav_company_search(data)

    print("SalesNav URL:", search_url)

    response = launch_company_search(search_url)

    container_id = response.get("containerId")

    request.container_id = container_id
    request.status = "Running"

    db.commit()

    background_tasks.add_task(
        poll_search_and_scrape,
        request.id,
        container_id
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
