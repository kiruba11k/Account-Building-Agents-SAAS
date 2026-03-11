from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from .database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)

    request_id = Column(Integer)

    full_name = Column(String)
    title = Column(String)

    company_name = Column(String)

    industry = Column(String)

    location = Column(String)

    linkedin_profile = Column(String)


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
