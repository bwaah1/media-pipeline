from worker import process_job


class FakeJob:
    def __init__(self):
        self.status = "NEW"


class FakeDB:
    def commit(self):
        pass

    def rollback(self):
        pass


def test_process_job_success(monkeypatch):
    job = FakeJob()
    db = FakeDB()

    monkeypatch.setattr("worker.call_external_api", lambda job: True)

    process_job(db, job)

    assert job.status == "DONE"

def test_process_job_failed(monkeypatch):
    job = FakeJob()
    db = FakeDB()

    monkeypatch.setattr("worker.call_external_api", lambda job: False)

    process_job(db, job)

    assert job.status == "FAILED"

def test_process_job_exception(monkeypatch):
    job = FakeJob()
    db = FakeDB()

    def crash(job):
        raise Exception("DB fail")

    monkeypatch.setattr("worker.call_external_api", crash)

    process_job(db, job)

    assert job.status == "FAILED"