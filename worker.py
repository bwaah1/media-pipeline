import time
from db import SessionLocal
from models import Job


def get_job():
    db = SessionLocal()

    job = db.query(Job).filter(Job.status == "NEW").first()

    if not job:
        return None

    job.status = "PROCESSING"
    db.commit()
    return job


def process(job):
    print("Processing:", job.source_url)
    time.sleep(2)


def run():
    while True:
        job = get_job()

        if not job:
            time.sleep(2)
            continue

        try:
            process(job)

            db = SessionLocal()
            job.status = "DONE"
            db.merge(job)
            db.commit()

        except Exception:
            db = SessionLocal()
            job.retry_count += 1
            job.status = "NEW"
            db.merge(job)
            db.commit()


if __name__ == "__main__":
    run()