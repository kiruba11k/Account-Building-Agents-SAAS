from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import LeadRequest, Company
from .phantom_service import launch_agent, get_container_status, fetch_container_output
import time
import pandas as pd

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def poll_and_store(request_id, container_id):
    db = SessionLocal()

    try:
        attempts = 0
        while attempts < 40:
            status = get_container_status(container_id).get("status")

            if status == "finished":
                output = fetch_container_output(container_id)
                results = output.get("data", [])

                request = db.query(LeadRequest).filter_by(id=request_id).first()

                for item in results:
                    company = Company(
                        request_id=request_id,
                        name=item.get("companyName"),
                        linkedin_url=item.get("companyUrl"),
                        website=item.get("website"),
                        industry=item.get("industry"),
                        headcount=item.get("companySize"),
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

    response = launch_agent(data)
    container_id = response.get("containerId")

    request.container_id = container_id
    request.status = "Running"
    db.commit()

    background_tasks.add_task(poll_and_store, request.id, container_id)

    return {"request_id": request.id}

@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    return db.query(LeadRequest).all()

@app.get("/api/download/{request_id}")
def download_csv(request_id: int, db: Session = Depends(get_db)):

    companies = db.query(Company).filter_by(request_id=request_id).all()

    data = [{
        "Company Name": c.name,
        "LinkedIn URL": c.linkedin_url,
        "Website": c.website,
        "Industry": c.industry,
        "Headcount": c.headcount,
        "Revenue": c.revenue,
        "Headquarters": c.headquarters
    } for c in companies]

    df = pd.DataFrame(data)

    file_path = f"/tmp/request_{request_id}.csv"
    df.to_csv(file_path, index=False)

    return FileResponse(file_path, filename=f"salesnav_{request_id}.csv")
