from sqlalchemy import Column, Integer, String, JSON
from .database import Base


class LeadRequest(Base):

    __tablename__ = "lead_requests"

    id = Column(Integer, primary_key=True)

    request_name = Column(String)

    status = Column(String)

    phase = Column(String)

    progress = Column(Integer)

    container_id = Column(String)

    total_results = Column(Integer)

    filters = Column(JSON)


class Company(Base):

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)

    request_id = Column(Integer)

    name = Column(String)

    domain = Column(String)

    website = Column(String)

    industry = Column(String)

    headcount = Column(String)

    revenue = Column(String)

    headquarters = Column(String)

    linkedin_url = Column(String)

    confidence_score = Column(String)
