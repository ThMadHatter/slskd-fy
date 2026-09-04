# Backend Logging Current State Assessment

## 1. Executive Summary

This document provides a comprehensive, evidence-based assessment of the current backend logging architecture in Track Portal (FastAPI backend). The assessment was conducted by examining application entry points, middleware, routers, background pollers, services, models, configuration files, scripts, and test suites across the codebase.

### Key Assessment Findings
* **Logging Framework:** The application exclusively uses Python standard library `logging` (`app/main.py:2`, `app/auth.py:2`, `app/routers/pages.py:2`). No third-party structured logging libraries such as `structlog` or `loguru` are present in `requirements.txt`.
* **Logger Hierarchy & Naming:** Loggers follow a hierarchical naming pattern rooted at `"track_portal"` (e.g., `"track_portal.auth"`, `"track_portal.pages"`, `"track_portal.poller"`), with one exception (`app/services/slskd.py:8`, which uses `logging.getLogger(__name__)`).
* **Format & Output:** Logs are emitted as unformatted or simple string-formatted text (`"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` in `app/main.py:38`). No JSON formatting or machine-parseable key-value formatting is implemented (`[OBS-001]` gap).
* **Correlation & Context:** There is **zero request or correlation ID tracking** across the HTTP request lifecycle or background tasks (`[OBS-002]` gap). No middleware injects `X-Request-ID` or attaches trace context to `request.state`.
* **Exception Visibility:** Exception handling relies heavily on `try...except Exception as e:` blocks that log exceptions via string formatting (`f"Error ... {e}"`) rather than capturing full stack traces via `logger.exception()` or `exc_info=True`. Across the entire codebase, `logger.exception` and `exc_info` are completely absent.
* **Sensitive Data Risk:** In `app/auth.py:95`, a randomly generated admin password is logged at `CRITICAL` log level (`logger.critical(f"NO ADMIN PASSWORD CONFIGURED. GENERATED RANDOM: {password}")`). While meant as a fallback notice, logging cleartext credentials to standard output poses an operational security risk.
* **Logging vs Print Statements:** Several background routines rely on raw `print(..., flush=True)` statements alongside standard logging (`app/services/downloads_poller.py:54`, `app/services/downloads_poller.py:185`), bypassing standard log handlers and output formatting.

---

## 2. Backend Architecture Relevant to Logging

The backend architecture is built on FastAPI and organized into distinct runtime layers:

```
                  +-------------------------------+
                  |      HTTP Client / Frontend   |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |  FastAPI App (app/main.py)    |  <-- setup_app_logging(), security_middleware
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  | Routers (app/routers/pages.py)|  <-- Endpoint handlers (logger: "track_portal.pages")
                  +---------------+---------------+
                                  |
            +---------------------+---------------------+
            |                     |                     |
            v                     v                     v
+-----------+-----------+ +-------+-------+ +-----------+-----------+
| Dependency Injection  | | Auth Service  | | Background Poller     |
| (app/dependencies.py) | | (app/auth.py) | | (downloads_poller.py)   |
+-----------+-----------+ +-------+-------+ +-----------+-----------+
            |                     |                     |
            v                     v                     v
+-----------+-----------+ +-------+-------+ +-----------+-----------+
|  Services Layer       | | Database (DB) | | Beets & External API  |
| (search, ranking, etc)| | (SQLAlchemy)  | | Clients (slskd, MB)   |
+-----------------------+ +---------------+ +-----------------------+
```

### Component Inventory & Boundary Mapping

| Component Boundary | Key Files & Entry Points | Log Instance / Name | Primary Observability Purpose |
| :--- | :--- | :--- | :--- |
| **App Entry Point & Lifespan** | `app/main.py:21-80` | `track_portal` | Lifecycle events, DB migrations, startup steps |
| **Router & Controller** | `app/routers/pages.py:38` | `track_portal.pages` | HTTP endpoint ingress/egress, query benchmark timing |
| **Authentication & Audit** | `app/auth.py:14` | `track_portal.auth` | Audit log writing, admin initialization, session validation |
| **Background Poller** | `app/services/downloads_poller.py:15` | `track_portal.poller` | Transfer polling loop, Beets CLI import execution, Ghost Peer stall detection |
| **Search Fallback Executor** | `app/services/fallback_search_executor.py:17` | `track_portal.fallback_search_executor` | Progressive query orchestration, tier execution |
| **Search Ranking Engine** | `app/services/search_ranking_service.py:9` | `track_portal.search_ranking` | Quality scoring, format/junk rejection logging |
| **Artist & Track Autocomplete**| `app/services/artist_service.py:8`<br>`app/services/track_service.py:8` | `track_portal.artist_service`<br>`track_portal.track_service` | MB & Lidarr API query fallback, score reporting |
| **External API Clients** | `app/services/slskd.py:8`<br>`app/services/musicbrainz_service.py:10`<br>`app/services/beets_service.py:6` | `app.services.slskd` (via `__name__`)<br>`track_portal.musicbrainz`<br>`track_portal.beets_service` | External HTTP requests, status codes, timeouts, JSON parsing |
| **Caching Layer** | `app/services/cache_service.py:8` | `track_portal.cache_service` | Cache hit/miss/expiry tracking, TTL logging |
| **Metadata & Media Utilities** | `app/services/duplicate_detector.py:10`<br>`app/services/tagger.py:10` | `track_portal.duplicate_detector`<br>`track_portal.tagger` | Hash calculation, mutagen FLAC/ID3 tag operations |
| **CLI & Audit Scripts** | `audit.py:14`<br>`validate_real_data.py:11` | `track_portal.audit`<br>Root logger | Offline E2E workflow validation, real-world data benchmarking |

---

## 3. Current Logging Libraries and Configuration

### 3.1 Dependencies & Libraries
Inspection of `requirements.txt:1-15` reveals standard Python dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `httpx`). No dedicated logging, tracing, or metrics frameworks (`structlog`, `loguru`, `opentelemetry-api`, `prometheus-client`) are present in `requirements.txt`. All logging relies strictly on standard Python `logging`.

### 3.2 Logger Setup
Centralized logging setup occurs in `app/main.py:23-39`:

```python
# app/main.py:23-39
def setup_app_logging():
    """
    Set up Track Portal logging. Executed inside lifespan startup
    to ensure Uvicorn does not overwrite our handlers.
    """
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear to avoid duplicates

    uvicorn_logger = logging.getLogger("uvicorn.error")
    if uvicorn_logger.handlers:
        for h in uvicorn_logger.handlers:
            logger.addHandler(h)
    else:
        # Fallback console handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(sh)
    logger.propagate = False
```

#### Key Characteristics:
1. **Execution Timing:** Called during the FastAPI `lifespan` startup phase (`app/main.py:55`).
2. **Handler Inheritance:** Checks `uvicorn.error` for existing handlers; if found, attaches Uvicorn's handlers to `track_portal`. Otherwise, creates a stdout `StreamHandler`.
3. **Propagation:** Sets `logger.propagate = False` on the `"track_portal"` logger.
4. **Child Loggers:** Child loggers (e.g., `logging.getLogger("track_portal.pages")`) inherit handlers from `"track_portal"` via Python standard logging propagation hierarchy.
5. **Inconsistency in `slskd.py`:** In `app/services/slskd.py:8`, the logger is declared as `logger = logging.getLogger(__name__)` (evaluating to `"app.services.slskd"`). Because `"app.services.slskd"` does not start with `"track_portal"`, it propagates to the root logger rather than `"track_portal"`, causing its formatting to bypass `setup_app_logging`.

### 3.3 Environment-Specific Configuration Analysis
* **Local Development:** Uses `uvicorn` CLI command (`CMD ["uvicorn", "app.main:app", ...]`). Output goes to stdout.
* **Automated Tests (`pytest`):** No custom logging configuration or `caplog` assertions exist in `tests/`. Pytest default log capturing intercepts output.
* **CI / Containerized Deployments (`Dockerfile`, `docker-compose.yml`):** Log stream is routed directly to stdout/stderr. Docker logs captures human-readable strings.
* **Staging / Production:** No environment-based logger switches or JSON formatting toggles (`LOG_LEVEL`, `LOG_FORMAT=json`) exist in `app/config.py`.

---

## 4. Request-Context Propagation

### 4.1 Request ID & Correlation Tracking
* **Current State:** **Absent.**
* **Architectural Rule Violation:** Violation of `[OBS-002]` (*End-to-End Correlation/Context ID Tracking* in `docs/architecture/08-OBSERVABILITY.md:13-18`), which requires a unique Correlation ID (e.g., UUIDv4) for every HTTP request or scheduled task to be injected into logging context and propagated across search providers, fallback steps, and slskd API clients.

### 4.2 HTTP Middleware Inspection
`app/main.py:94-98` defines a single HTTP middleware:

```python
# app/main.py:94-98
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request.state.user = None
    response = await call_next(request)
    return response
```

* The middleware sets `request.state.user = None` but does not generate or attach a `request_id` / `correlation_id`.
* The middleware does not measure HTTP request duration or log request ingress/egress.
* Log messages emitted within router handlers (e.g., `app/routers/pages.py:201`) do not carry request metadata (IP address, path, method, user ID, or trace context).

### 4.3 Context Propagation Across Async Boundaries
When an HTTP request triggers progressive search steps in `app/routers/pages.py:207` or enqueues background work in `app/services/downloads_poller.py:311`, context is passed strictly via positional/keyword arguments (`artist`, `track`, `search_id`). Contextvars (`contextvars.ContextVar`) are not utilized anywhere in the backend codebase.

---

## 5. Exception Propagation and Ownership

### 5.1 Exception Logging Patterns
Across the backend, exception handling follows a defensive "catch and log string" pattern. Full tracebacks are consistently suppressed or omitted.

#### Typical Exception Handling Snippets
1. **Database Migration Failures (`app/main.py:48`):**
   ```python
   except Exception as e:
       logger.error(f"Error running database migrations: {e}")
   ```
2. **Healthcheck DB Connection Failures (`app/main.py:109`):**
   ```python
   except Exception as e:
       logger.error(f"Healthcheck database error: {e}")
       raise HTTPException(status_code=500, detail=f"Unhealthy: {e}")
   ```
3. **Search Response Fetch Warnings (`app/routers/pages.py:224`):**
   ```python
   except Exception as e:
       logger.warning(f"Error fetching search responses for {search_id}: {e}")
   ```
4. **Beets Import Failures (`app/services/downloads_poller.py:62`):**
   ```python
   except Exception as e:
       logger.error(f"Error executing Beets import process: {e}")
   ```
5. **Background Poller Main Loop (`app/services/downloads_poller.py:302`):**
   ```python
   except Exception as e:
       logger.error(f"Error in background polling task: {e}")
   ```

### 5.2 Key Deficiencies in Exception Handling
* **No `logger.exception()` Usage:** A grep search across `app/` confirms `logger.exception` occurs **0 times**.
* **No `exc_info=True` Usage:** A grep search across `app/` confirms `exc_info` occurs **0 times**.
* **Loss of Stack Traces:** When unexpected exceptions occur (e.g., database connection reset, unexpected JSON parsing error, HTTP timeout), only the string representation of the exception (`str(e)`) is logged. The stack trace, line number, and root cause exception chain are lost.
* **HTTP Exception Mapping:** Unhandled exceptions that bubble up to FastAPI return standard 500 responses without an associated log entry containing a trace correlation identifier.

---

## 6. Representative Request or Job Flows

### Flow 1: Successful HTTP Request (Search Pipeline Workflow)
**Endpoint:** `POST /api/search` (`app/routers/pages.py:164-323`)

```
Client -> POST /api/search
  |
  +--> [pages.py:181] INFO: "Enriching search artist 'x' -> 'y' via MusicBrainz"
  +--> [pages.py:201] INFO: "BENCHMARK - Generated progressive queries for 'x' / 'y': ['...']"
  +--> [pages.py:207] INFO: "Incremental Search - Executing query: '...' (timeout_sec=15, wait_until_complete=False)"
  +--> [slskd.py:35] DEBUG: "Initiating slskd search for query: '...'" (Uses app.services.slskd logger)
  +--> [pages.py:233] INFO: "Search {search_id} state reached final status 'Completed' (isComplete=True) after 1.23s"
  +--> [pages.py:242] INFO: "BENCHMARK - Query '...' search completed in 1.25s with 14 peer responses"
  +--> Stream responses to client via StreamingResponse
```

* **Observation:** Log entries exist for benchmark execution milestones, but they lack a common request ID. If two concurrent users search simultaneously, log lines from different searches interleave unpredictably without correlation tags.

---

### Flow 2: Expected Application Failure (Download Enqueue Failure)
**Endpoint:** `POST /api/download` (`app/routers/pages.py:326-363`)

```
Client -> POST /api/download (payload: {username: "peer1", filename: "song.mp3"})
  |
  +--> [pages.py:334] INFO: "DOWNLOAD_REQUESTED - Username: 'peer1', Filename: 'song.mp3'"
  +--> [slskd.py:112] Calls slskd_client.enqueue_download("peer1", "song.mp3", 1024)
  |      +-- External slskd service returns 400 Bad Request or HTTP error
  |
  +--> [pages.py:358] ERROR: "Download request failed for file: 'song.mp3'"
  +--> [pages.py:359] raise HTTPException(status_code=500, detail="Failed to enqueue download in slskd")
```

* **Observation:** The error log at `pages.py:358` logs the filename but omits the peer username, exception type, HTTP status code returned by slskd, or response body details. Troubleshooting why the download failed requires reading slskd's internal logs independently.

---

### Flow 3: Unexpected Exception / External Dependency Failure (Ghost Peer Poller Failure)
**Background Worker:** `poll_downloads` (`app/services/downloads_poller.py:173-305`)

```
poll_downloads loop tick
  |
  +--> [downloads_poller.py:185] PRINT: "[AUDIT_POLLER] Loop Step: active downloads found count=1"
  +--> [downloads_poller.py:187] Calls slskd_client.get_downloads()
  |      +-- Network connection drop to slskd container (httpx.ConnectError)
  |
  +--> [downloads_poller.py:302] ERROR: "Error in background polling task: All connection attempts failed"
  +--> Loop sleeps 10s and retries
```

* **Observation:** `str(e)` is printed, but `exc_info=True` is not set. Stack trace showing whether the failure occurred during socket connect, HTTP header parsing, or JSON deserialization is completely missing.

---

## 7. Sensitive-Data Risks

An audit of string formatting in log statements across `app/` identified the following sensitive data handling practices:

### 7.1 Identified Risks & Cleartext Credentials

1. **Cleartext Random Admin Password Logging (`app/auth.py:94-96`):**
   ```python
   # app/auth.py:94-96
   logger.critical("*" * 60)
   logger.critical(f"NO ADMIN PASSWORD CONFIGURED. GENERATED RANDOM: {password}")
   logger.critical("*" * 60)
   ```
   * **Risk Level:** **High.** When no `ADMIN_PASSWORD` env variable is set on first launch, `init_admin_user` generates a random password and writes it to standard output at `CRITICAL` log level. In log aggregator systems, container monitoring platforms, or persistent log files, this temporary admin password remains permanently readable.

2. **slskd API Key Masking (`audit.py:34`):**
   ```python
   # audit.py:34
   logger.info(f"Using slskd API Key: {settings.SLSKD_API_KEY[:4]}...{settings.SLSKD_API_KEY[-4:] if len(settings.SLSKD_API_KEY) > 8 else ''}")
   ```
   * **Assessment:** Good practice applied in offline audit script (masks center digits of API key). However, in `app/services/slskd.py`, API key header values are attached to `httpx.AsyncClient` without explicit log dumping of headers.

3. **User Tokens / Passwords in Router Logging:**
   * In `app/routers/pages.py:469-563` (`login` endpoint), user passwords and JWT secret keys are **not** logged. User log actions log only `username` and `client_ip` (`app/routers/pages.py:553`), complying with privacy principles.

---

## 8. Existing Strengths

Despite current observability gaps, the backend demonstrates several solid architectural foundation points:

1. **Structured Domain Event Logging:** Certain critical workflow state transitions use explicit event prefixes, making log filtering straightforward (e.g., `DOWNLOAD_REQUESTED`, `DOWNLOAD_COMPLETED`, `BENCHMARK`, `AUDIT_POLLER`).
2. **Centralized Lifecycle Logging:** `app/main.py:52-73` cleanly isolates application lifespan phases (DB migrations, admin initialization, background poller startup) with step-by-step progress logging.
3. **Domain-Specific Logger Hierarchy:** Most modules instantiate dedicated child loggers using the `"track_portal.<module>"` convention (e.g., `"track_portal.auth"`, `"track_portal.pages"`, `"track_portal.search_ranking"`), laying a clean foundation for per-module log level filtering.
4. **No Raw Credential Body Dumps:** HTTP endpoints in `app/routers/pages.py` do not log raw HTTP request bodies, authorization headers, or cookie values.

---

## 9. Preliminary Risks and Inconsistencies

The following table summarizes all identified gaps, risks, and inconsistencies in the backend logging state:

| ID | Category | Description | Source File Reference | Impact |
| :--- | :--- | :--- | :--- | :--- |
| **GAP-01** | **Observability** | No JSON or key-value structured log formatter (`[OBS-001]` rule violation). Logs emit unparsed human text. | `app/main.py:38` | Automated log parsers and SIEM systems cannot index field metadata reliably. |
| **GAP-02** | **Tracing** | Missing Correlation ID / Request ID tracking across HTTP endpoints and async workflows (`[OBS-002]` rule violation). | `app/main.py:94-98`, `app/routers/pages.py:164` | Inability to trace concurrent user queries or link client HTTP errors to background jobs. |
| **GAP-03** | **Exception Tracking** | Absence of `logger.exception()` or `exc_info=True` across all exception handlers. | Entire `app/` codebase (0 occurrences) | Deep stack trace details are lost on unexpected errors; debugging relies on exception string summaries. |
| **GAP-04** | **Logger Scope Inconsistency** | `app/services/slskd.py` uses `logging.getLogger(__name__)` (`"app.services.slskd"`) instead of `"track_portal.slskd"`. | `app/services/slskd.py:8` | Bypasses `track_portal` parent logger settings, propagation control, and custom handlers defined in `app/main.py`. |
| **GAP-05** | **Security** | Plaintext admin password printed to `CRITICAL` log output during auto-initialization. | `app/auth.py:95` | Administrative credentials exposed in log sinks/containers. |
| **GAP-06** | **Unstructured Bypasses** | Raw `print(..., flush=True)` calls used in background routines alongside standard loggers. | `app/services/downloads_poller.py:54,185` | Statements bypass standard log formatters, timestamps, log levels, and log destinations. |
| **GAP-07** | **External Client Visibility** | Lack of HTTP status code, response timing, and request target URI context in external client failure logs. | `app/services/slskd.py:40,75,115`, `app/services/beets_service.py:25` | Difficult to diagnose network timeouts vs HTTP 4xx/5xx responses from slskd or Beets. |

---

## 10. Open Questions

The following questions cannot be definitively answered from repository code alone and depend on operational/deployment context:

1. **Log Aggregation Strategy:** What log ingestion platform (e.g., Datadog, Grafana Loki, Elastic/ELK, CloudWatch) will consume stdout in production? (Determines whether single-line JSON or specific field schemas are preferred).
2. **Log Retention & Disk Limits:** Is stdout redirected to a persistent log file on host mounts (`/mnt/music/Config/track-portal/logs`), or managed exclusively via Docker container logging drivers (`json-file` log-opt max-size)?
3. **Environment Configuration Controls:** Should log levels (`DEBUG`, `INFO`, `WARNING`) be configurable dynamically via environment variable (`LOG_LEVEL=DEBUG`) in `app/config.py`?
