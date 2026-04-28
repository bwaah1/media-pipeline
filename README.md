# Media Pipeline System Design

## Table of Contents

- [1. Root Cause Analysis](#1-root-cause-analysis)
- [2. Proposed Architecture](#2-proposed-architecture)
- [3. Database Schema Improvements](#3-database-schema-improvements)
- [4. Monitoring & Observability](#4-monitoring--observability)
- [5. Scaling Strategy](#5-scaling-strategy-x10-load)

---

## 1. Root Cause Analysis

### 1. Duplicate Scraper Records

**Cause:**
- No `UNIQUE` constraint on `source_url`
- No idempotency check before insert

**Fix:**
- Add `UNIQUE(source_url)` constraint
- Or use UPSERT logic: `INSERT ... ON CONFLICT DO NOTHING`

---

### 2. Downloader Stuck on NEW

**Cause:**
- No job locking mechanism
- Multiple workers pick the same task simultaneously

**Fix:**
- Use DB-level locking: `SELECT ... FOR UPDATE SKIP LOCKED`
- Enforce status lifecycle: `NEW → PROCESSING → DONE`
- Add timeout / heartbeat mechanism

---

### 3. Poster Runs Twice (Cron Duplication)

**Cause:**
- No distributed locking between cron instances

**Fix:**
- Redis distributed lock: `SET key NX EX`
- Or DB lock table with a unique constraint per job type

---

### 4. Missing `post_id` in Analytics

**Cause:**
- Async writes without transactional consistency
- No foreign key between `jobs` and `analytics`

**Fix:**
- Add FK: `analytics.job_id → jobs.id`
- Wrap post + analytics write in a single transaction
- Add retry mechanism for failed writes

---

### 5. External API Failures Lose Jobs

**Cause:**
- No retry system
- No persistent failure state
- No Dead Letter Queue (DLQ)

**Fix:**
- Add `retry_count` column to `jobs`
- Implement exponential backoff retry
- Route exhausted jobs to a DLQ table for manual reprocessing

---

## 2. Proposed Architecture

### Current Flow

```
scraper → DB (jobs)
              ↓
    FastAPI creates job record
              ↓
    worker.py polls & consumes
              ↓
    call_external_api()
              ↓
         DONE / FAILED
```

### Implemented Improvements

| Area | Detail |
|---|---|
| **Retry system** | `MAX_RETRIES = 3`, retry loop with delay, job marked `FAILED` after exhaustion |
| **Error handling** | `try/except` around worker loop, `db.rollback()` on failure, worker never crashes |
| **Job lifecycle** | `NEW → PROCESSING → DONE / FAILED` |

### Recommended Production Architecture

```
scraper → Redis Queue
               ↓
     Celery / RQ workers (horizontal)
               ↓
     call_external_api()
          ↓         ↓
        DONE      FAILED → DLQ
```

- Workers consume from queue (no DB polling)
- Idempotency keys for safe retries
- Stateless workers for horizontal scaling

---

## 3. Database Schema Improvements

### Current Schema

```sql
jobs:
  id         INTEGER PRIMARY KEY
  status     TEXT  -- NEW | DONE | FAILED
  source_url TEXT
```

### Improved Schema

```sql
-- Add retry and locking support
ALTER TABLE jobs ADD COLUMN retry_count  INT       DEFAULT 0;
ALTER TABLE jobs ADD COLUMN locked_at    TIMESTAMP NULL;
ALTER TABLE jobs ADD COLUMN updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Prevent duplicate URLs
CREATE UNIQUE INDEX idx_jobs_source_url ON jobs(source_url);

-- Dead Letter Queue for permanently failed jobs
CREATE TABLE dead_letter_queue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER,
    error      TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Monitoring & Observability

### Health Checks

- `GET /health` — FastAPI endpoint
- DB connection check on startup
- Worker heartbeat via `last_seen` timestamp

### Logging

- Structured JSON logs
- `job_id` included in every log line
- Log status transitions (`NEW → PROCESSING`, etc.)

### Alerts

| Condition | Threshold |
|---|---|
| Spike in `FAILED` jobs | > N failures / minute |
| Worker stuck | No heartbeat for > 60s |
| DLQ size | Exceeds configured limit |

### Dead Letter Queue (DLQ)

- Stores permanently failed jobs after retry exhaustion
- Allows manual inspection and reprocessing
- Prevents silent data loss

---

## 5. Scaling Strategy (x10 Load)

### Current Bottlenecks

- DB polling in worker loop
- No queue system — workers compete for jobs
- Single worker instance

### Improvements

**1. Queue-based processing**
Replace DB polling with Redis Queue (RQ) or Celery. Workers subscribe to the queue instead of scanning the DB.

**2. Horizontal scaling**
Run multiple stateless worker instances behind a load balancer. No shared mutable state between workers.

**3. Database optimization**
- Add indexes on `status` and `source_url`
- Avoid full table scans in worker polling queries

**4. Locking strategy**
- Use `SELECT ... FOR UPDATE SKIP LOCKED` for DB-backed queues
- Or Redis distributed locks for cross-service coordination

**5. Idempotency**
- Enforce `UNIQUE(source_url)` to prevent duplicate ingestion
- Use idempotency keys on API calls for safe retries