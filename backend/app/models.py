from sqlalchemy import Column, Integer, String, JSON
from .database import Base


class LeadRequest(Base):
    __tablename__ = "lead_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_name = Column(String)
    status = Column(String)
    phase = Column(String)
    progress = Column(Integer, default=0)
    container_id = Column(String)
    total_results = Column(Integer, default=0)
    filters = Column(JSON)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, index=True)

    # optional normalized fields for app usage
    name = Column(String)
    domain = Column(String)
    website = Column(String)
    industry = Column(String)
    headcount = Column(String)
    revenue = Column(String)
    headquarters = Column(String)
    linkedin_url = Column(String)
    confidence_score = Column(String)

    # source of truth
    raw_data = Column(JSON)
