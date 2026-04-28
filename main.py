from fastapi import FastAPI
from pydantic import BaseModel

from db import engine, SessionLocal
from models import Base, Job

Base.metadata.create_all(bind=engine)

app = FastAPI()


class JobCreate(BaseModel):
    source_url: str


@app.post("/jobs")
def create_job(data: JobCreate):
    db = SessionLocal()

    try:
        job = Job(source_url=data.source_url)
        db.add(job)
        db.commit()
        return {"status": "created"}
    except:
        db.rollback()
        return {"status": "duplicate"}


@app.get("/health")
def health():
    return {"status": "ok"}