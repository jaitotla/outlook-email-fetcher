# Async Architecture & Queue Analysis

## How Multiple Requests Are Handled

FastAPI runs on a single-threaded async event loop (uvicorn). All `async def` route handlers share this loop. If any handler blocks the loop with synchronous I/O (e.g., `sqlite3.connect`, `requests.get`, `llm.invoke`), ALL concurrent requests freeze until it finishes.

### Before These Fixes
- `/api/label-email`: called `label_pipeline.label_and_store_thread()` synchronously → blocked event loop for entire LLM call duration (~2–10s per email)
- `/api/chat-with-thread`: called `chat_pipeline.process_and_chat()` synchronously → could block for 30–300s while embedding old emails
- `/api/draft-with-attachments`: called `draft_pipeline.process_email_request()` which mixed async/sync incorrectly

**Effect:** Under the 1-minute background monitor sending multiple emails, the server would queue up LLM calls synchronously. Each new request would find the loop blocked, causing 504 gateway timeouts.

### After These Fixes
- Short operations (file I/O, cleaning, storing) remain synchronous but are offloaded via `run_in_executor`
- Heavy operations (LLM classification, embedding, draft generation) run in background via FastAPI `BackgroundTasks`
- Routes return `job_id` immediately (< 5ms), clients poll `/api/job-status/{job_id}`

## How Multiple Emails Are Processed

### Background Monitor (GAS)
The `monitorEmails()` function in `BackgroundEmailMonitor.gs` processes emails **one message at a time** in a sequential `for` loop. Each message triggers:
1. `sendEmailToServer()` → POST `/api/label-email` (1 message per call)
2. `sendAttachmentsToServer()` → POST `/api/store-attachments` (all attachments of that message in one call)

There is **no batching** across messages. Each GAS execution handles at most 100 threads, iterates messages within them one by one.

### Old Email Processing (Chat/Draft pipelines)
When `ChatWithThreadPipeline.process_and_chat()` is called for a thread:
1. It reads the stored JSON file (`{thread_id}.json`) which contains **all messages as a list**
2. It iterates through the list, embedding each unprocessed message one at a time
3. It iterates through attachment files in the thread directory, processing one at a time
4. Processing state is tracked per-message in SQLite (`chat_thread_processing.db`)

**Old emails come as a list** (the full thread JSON), not one at a time. The pipeline iterates them internally. There is **no queue** — the entire loop runs synchronously before returning.

### After These Fixes (Job Queue)
Old email processing now runs in a background task:
1. Client POSTs → receives `job_id` immediately
2. Background thread runs the full pipeline (embedding loop, LLM call)
3. Client polls `/api/job-status/{job_id}` until `status == "done"`

This means multiple users can trigger processing concurrently without blocking each other.

## Concurrency Limits
- `BackgroundTasks` uses the same thread pool as `run_in_executor` (default: `min(32, os.cpu_count() + 4)` threads)
- For high-concurrency deployments, replace `_job_store` dict with Redis and use Celery or ARQ for the task queue
- SQLite has write-lock contention under concurrent access — for production, migrate to PostgreSQL
