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
    total_results = Column(Integer, default=0)
    agent_type = Column(String, default="salesnav")
    filters = Column(JSON)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, index=True)

    company_url = Column(String)
    company_name = Column(String)
    description = Column(String)
    company_id = Column(String)
    regular_company_url = Column(String)
    industry = Column(String)
    employees_count = Column(String)
    employee_count_range = Column(String)
    logo_url = Column(String)
    is_hiring = Column(String)
    query = Column(String)
    timestamp = Column(String)
    search_account_profile_id = Column(String)
    search_account_profile_name = Column(String)

    raw_data = Column(JSON)
