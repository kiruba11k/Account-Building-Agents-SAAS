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

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()


# -------------------------------------------------
# Extract LinkedIn Company URLs from search results
# -------------------------------------------------

def extract_company_urls(results):

    urls = []

    for item in results:
        if item.get("linkedInCompanyUrl"):
            urls.append(item["linkedInCompanyUrl"])

    return urls


# -------------------------------------------------
# Database session dependency
# -------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# Poll SalesNav Search Phantom
# -------------------------------------------------

def poll_search_and_scrape(request_id, container_id):

    db = SessionLocal()

    try:

        attempts = 0

        while attempts < 40:

            status_response = get_container_status(container_id)
            status = status_response.get("status")

            if status == "finished":

                output = fetch_container_output(container_id)
                search_results = output.get("data", [])

                company_urls = extract_company_urls(search_results)

                if not company_urls:

                    request = db.query(LeadRequest).filter_by(id=request_id).first()
                    request.status = "Completed"
                    request.total_results = 0
                    db.commit()

                    return

                print(f"Found {len(company_urls)} company URLs")

                # Launch second Phantom (company scraper)
                scraper_response = launch_company_scraper(company_urls)

                scraper_container = scraper_response.get("containerId")

                # Poll scraper results
                poll_scraper_and_store(request_id, scraper_container)

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
# Poll Account Scraper Phantom
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

                    company = Company(
                        request_id=request_id,
                        name=item.get("name"),
                        linkedin_url=item.get("linkedInCompanyUrl"),
                        website=item.get("website"),
                        industry=item.get("industry"),
                        headcount=item.get("employeeCountRange"),
                        revenue=item.get("revenue"),
                        headquarters=item.get("location")
                    )

                    db.add(company)

                request.status = "Completed"
                request.total_results = len(results)

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
# Launch Sales Navigator Agent
# -------------------------------------------------

@app.post("/api/run-salesnav")
def run_salesnav(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):

    request = LeadRequest(
        request_name=data.get("request_name"),
        status="Launching",
        filters=data
    )

    db.add(request)
    db.commit()
    db.refresh(request)

    # Build Sales Navigator search URL
    search_url = build_salesnav_company_search(data)

    print("Generated SalesNav URL:", search_url)

    # Launch Search Phantom
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
# Get all requests
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
        "Name": c.name,
        "Industry": c.industry,
        "Location": c.headquarters,
        "Website": c.website,
        "Employees": c.headcount,
        "Revenue": c.revenue,
        "LinkedIn": c.linkedin_url
    } for c in companies]

    df = pd.DataFrame(data)

    file_path = f"/tmp/request_{request_id}.csv"

    df.to_csv(file_path, index=False)

    return FileResponse(
        file_path,
        filename=f"salesnav_{request_id}.csv",
        media_type="text/csv"
    )
