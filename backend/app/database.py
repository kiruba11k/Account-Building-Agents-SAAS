from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from .database import Base


class LeadRequest(Base):
    __tablename__ = "lead_requests"

    id = Column(Integer, primary_key=True, index=True)

    request_name = Column(String)
    status = Column(String, default="Queued")

    container_id = Column(String)

    total_results = Column(Integer, default=0)

    filters = Column(JSON)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)

    request_id = Column(Integer, ForeignKey("lead_requests.id"))

    name = Column(String)

    linkedin_url = Column(String)
    website = Column(String)

    industry = Column(String)

    headcount = Column(String)

    revenue = Column(String)

    headquarters = Column(String)
