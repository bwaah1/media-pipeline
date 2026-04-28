import time
import random
from db import SessionLocal
from models import Job
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_RETRIES = 3
POLL_INTERVAL = 2

def call_external_api(job):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if random.random() < 0.5:
                raise Exception("API error")

            return True

        except Exception as e:
            print(f"[API] attempt {attempt} failed: {e}")

            if attempt < MAX_RETRIES:
                sleep_time = 2 ** attempt  # exponential backoff
                time.sleep(sleep_time)

    return False

def get_job(db: Session):
    """
    Беремо тільки одну NEW задачу.
    У production тут додається SKIP LOCKED (PostgreSQL/MariaDB 10+).
    """
    return (
        db.query(Job)
        .filter(Job.status == "NEW")
        .order_by(Job.id.asc())
        .first()
    )

def process_job(db: Session, job: Job):
    try:
        job.status = "PROCESSING"
        db.commit()

        ok = call_external_api(job)

        if ok:
            job.status = "DONE"
        else:
            job.status = "FAILED"

        db.commit()

    except Exception as e:
        print(f"[JOB ERROR] {e}")
        db.rollback()

        # safety fallback
        job.status = "FAILED"
        db.commit()

def run():
    print("Worker started...")

    while True:
        db = SessionLocal()

        try:
            job = get_job(db)

            if not job:
                db.close()
                time.sleep(POLL_INTERVAL)
                continue

            process_job(db, job)

        except Exception as e:
            print(f"[WORKER ERROR] {e}")
            db.rollback()
            time.sleep(POLL_INTERVAL)

        finally:
            db.close()

if __name__ == "__main__":
    run()