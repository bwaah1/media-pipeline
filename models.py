from sqlalchemy import Column, Integer, String, Text
from db import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    source_url = Column(Text, unique=True)

    status = Column(String, default="NEW")
    retry_count = Column(Integer, default=0)