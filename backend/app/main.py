import json
import time
import threading
import pandas as pd

from fastapi import FastAPI, Depends, BackgroundTasks
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
    fetch_container_output,
    fetch_container_results
)

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def resume_pending_jobs():
    db = SessionLocal()
    try:
        pending = db.query(LeadRequest).filter(LeadRequest.status == "Running").all()

        for job in pending:
            print("Resuming job:", job.id)
            threading.Thread(
                target=poll_search_and_store,
                args=(job.id, job.container_id),
                daemon=True
            ).start()
    finally:
        db.close()


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


def _pick_first(item, keys):
    for key in keys:
        if key in item:
            value = item.get(key)
            if value is not None and str(value).strip() != "":
                return value
    return None


def _extract_company_fields(item: dict):
    linkedin_url = _pick_first(item, [
        "regularCompanyUrl",
        "companyUrl",
        "companyLinkedinUrl",
        "linkedInCompanyUrl",
        "linkedinUrl",
        "linkedin_url"
    ])

    website = _pick_first(item, [
        "website",
        "companyWebsite",
        "companyDomain",
        "domain"
    ])

    name = _pick_first(item, [
        "companyName",
        "name"
    ])

    industry = _pick_first(item, [
        "industry",
        "companyIndustry"
    ])

    headcount = _pick_first(item, [
        "employeesCount",
        "employeeCount",
        "employeeCountRange",
        "headcount",
        "companySize",
        "employees"
    ])

    revenue = _pick_first(item, [
        "revenue",
        "companyRevenue"
    ])

    headquarters = _pick_first(item, [
        "headquarters",
        "location",
        "companyLocation",
        "companyHeadquarters"
    ])

    return {
        "linkedin_url": linkedin_url,
        "website": website,
        "name": name,
        "industry": industry,
        "headcount": headcount,
        "revenue": revenue,
        "headquarters": headquarters,
    }


def _looks_like_real_company(item: dict) -> bool:
    if not isinstance(item, dict) or not item:
        return False

    if item.get("companyName") and (item.get("companyUrl") or item.get("regularCompanyUrl")):
        return True

    keys_lower = {str(k).strip().lower() for k in item.keys() if k is not None}

    expected = {
        "companyurl",
        "companyname",
        "description",
        "companyid",
        "regularcompanyurl",
        "industry",
        "employeescount",
        "employeecountrange",
        "logourl",
        "ishiring",
        "query",
        "timestamp",
        "searchaccountprofileid",
        "searchaccountprofilename",
    }

    return len(keys_lower.intersection(expected)) >= 2


def poll_search_and_store(request_id, container_id):
    db = SessionLocal()

    try:
        request = db.query(LeadRequest).filter_by(id=request_id).first()
        if not request:
            print("Request not found:", request_id)
            return

        request.phase = "searching"
        request.progress = 25

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
                try:
                    results = fetch_container_results(container_id)
                    print("Fetched results type:", type(results))
                    print("Fetched results count:", len(results) if isinstance(results, list) else "not-list")
                    print("Fetched results sample:", results[:2] if isinstance(results, list) else results)
                except Exception as e:
                    print("Fetch results error:", e)
                    results = []

                request.phase = "processing"
                request.progress = 70
                db.commit()

                seen_fingerprints = set()
                inserted = 0

                for item in results:
                    if not isinstance(item, dict):
                        continue

                    if not item:
                        continue

                    if not _looks_like_real_company(item):
                        continue

                    extracted = _extract_company_fields(item)

                    linkedin_url = extracted["linkedin_url"]
                    website = extracted["website"]
                    name = extracted["name"]
                    industry = extracted["industry"]
                    headcount = extracted["headcount"]
                    revenue = extracted["revenue"]
                    headquarters = extracted["headquarters"]

                    domain = extract_domain(website)
                    confidence = calculate_confidence(item)

                    normalized_linkedin = (linkedin_url or "").strip().lower()
                    normalized_domain = (domain or "").strip().lower()
                    normalized_name = (name or "").strip().lower()

                    fingerprint = None
                    if normalized_linkedin:
                        fingerprint = f"linkedin:{normalized_linkedin}"
                    elif normalized_domain and normalized_domain != "linkedin.com":
                        fingerprint = f"domain:{normalized_domain}"
                    elif normalized_name:
                        fingerprint = f"name:{normalized_name}"

                    if fingerprint and fingerprint in seen_fingerprints:
                        continue

                    company = Company(
                        request_id=request_id,
                        name=name,
                        linkedin_url=linkedin_url,
                        website=website,
                        domain=domain,
                        industry=industry,
                        headcount=str(headcount) if headcount is not None else None,
                        revenue=str(revenue) if revenue is not None else None,
                        headquarters=headquarters,
                        confidence_score=str(confidence) if confidence is not None else None,
                        raw_data=item
                    )

                    db.add(company)
                    inserted += 1

                    if fingerprint:
                        seen_fingerprints.add(fingerprint)

                db.commit()
                print("Inserted companies:", inserted)

                request.total_results = db.query(Company).filter_by(request_id=request_id).count()

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

    except Exception as e:
        print("poll_search_and_store fatal error:", e)
        try:
            request = db.query(LeadRequest).filter_by(id=request_id).first()
            if request:
                request.status = "Failed"
                request.phase = "failed"
                request.progress = 100
                db.commit()
        except Exception as inner_e:
            print("Failed to update request status:", inner_e)

    finally:
        db.close()


@app.post("/api/run-salesnav")
def run_salesnav(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    request = LeadRequest(
        request_name=data.get("request_name"),
        status="Launching",
        phase="searching",
        progress=10,
        total_results=0,
        filters=data
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
            "clear_cache_response": clear_cache_response
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
        "search_url": search_url,
        "container_id": str(container_id),
        "clear_output_response": clear_output_response,
        "clear_cache_response": clear_cache_response
    }


@app.get("/api/request/{request_id}")
def get_request_status(request_id: int, db: Session = Depends(get_db)):
    request = db.query(LeadRequest).filter_by(id=request_id).first()

    if not request:
        return {"error": "request not found"}

    return {
        "id": request.id,
        "status": request.status,
        "phase": request.phase,
        "progress": request.progress,
        "total_results": request.total_results,
        "container_id": request.container_id
    }


@app.get("/api/results/{request_id}")
def get_results(request_id: int, page: int = 1, limit: int = 50, db: Session = Depends(get_db)):
    offset = (page - 1) * limit
    query = db.query(Company).filter_by(request_id=request_id)

    rows = query.offset(offset).limit(limit).all()
    total = query.count()

    results = []
    for row in rows:
        item = _model_to_dict(row)
        if row.raw_data:
            item["raw_data"] = row.raw_data
        results.append(item)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "results": results
    }


@app.get("/api/requests")
def get_requests(db: Session = Depends(get_db)):
    rows = db.query(LeadRequest).all()
    return [_model_to_dict(row) for row in rows]


@app.get("/api/download/{request_id}")
def download_file(request_id: int, format: str = "csv", db: Session = Depends(get_db)):
    companies = db.query(Company).filter_by(request_id=request_id).all()

    if not companies:
        return JSONResponse(
            status_code=404,
            content={
                "error": "No results found for this request_id",
                "request_id": request_id
            }
        )

    output_format = (format or "csv").strip().lower()

    export_rows = []
    for c in companies:
        if c.raw_data and isinstance(c.raw_data, dict):
            export_rows.append(dict(c.raw_data))
        else:
            export_rows.append({
                "id": c.id,
                "request_id": c.request_id,
                "name": c.name,
                "domain": c.domain,
                "website": c.website,
                "industry": c.industry,
                "headcount": c.headcount,
                "revenue": c.revenue,
                "headquarters": c.headquarters,
                "linkedin_url": c.linkedin_url,
                "confidence_score": c.confidence_score
            })

    if output_format == "json":
        file_path = f"/tmp/request_{request_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_rows, f, ensure_ascii=False, indent=2)

        return FileResponse(
            file_path,
            filename=f"salesnav_{request_id}.json",
            media_type="application/json"
        )

    df = pd.json_normalize(export_rows)

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


@app.get("/api/debug/container/{container_id}")
def debug_container(container_id: str):
    status = get_container_status(container_id)
    output = fetch_container_output(container_id)
    results = fetch_container_results(container_id)

    return {
        "status_response": status,
        "output_response": output,
        "parsed_result_count": len(results) if isinstance(results, list) else None,
        "parsed_sample": results[:2] if isinstance(results, list) else results,
    }


@app.get("/api/debug/request/{request_id}")
def debug_request(request_id: int, db: Session = Depends(get_db)):
    request = db.query(LeadRequest).filter_by(id=request_id).first()

    if not request:
        return {"error": "request not found"}

    if not request.container_id:
        return {
            "request_id": request.id,
            "status": request.status,
            "error": "missing container_id"
        }

    status = get_container_status(request.container_id)
    output = fetch_container_output(request.container_id)
    results = fetch_container_results(request.container_id)
    companies = db.query(Company).filter_by(request_id=request_id).count()

    return {
        "request_id": request.id,
        "request_status": request.status,
        "phase": request.phase,
        "container_id": request.container_id,
        "phantom_status": status,
        "phantom_output_keys": list(output.keys()) if isinstance(output, dict) else None,
        "parsed_result_count": len(results) if isinstance(results, list) else None,
        "parsed_sample": results[:2] if isinstance(results, list) else results,
        "db_company_count": companies,
    }
