# Data and State Management

To support robust, non-blocking telemetry and search optimization, this document establishes strict standards for data modeling, state operations, caching strategies, and data access separation.

## Core Rules & State Standards

### [DAT-001] Non-Blocking Telemetry & History Writes
Database writes for audit logging, search history caching, and search debug diagnostics must never block or slow down the main user-interactive execution threads or API responses.
* **Requirements:**
  * Asynchronous handlers or background tasks (e.g. FastAPI's `BackgroundTasks`) must be used when recording search history logs, analytics data, or diagnostic benchmark outcomes.
  * DB write locks on sqlite must be handled gracefully with an appropriate connection timeout (e.g., `timeout=30.0` inside sqlite connection parameters) and WAL (Write-Ahead Logging) mode enabled to allow parallel reads and writes.

### [DAT-002] Unified Caching Policies
All local search engine results and autocomplete metadata must utilize a unified caching strategy with clear time-to-live (TTL) limits and eviction rules.
* **Requirements:**
  * Every entry written to `cache_entries` must define a clear `expires_at` timestamp.
  * The cache service must implement a proactive eviction sweep task running on a schedule to purge expired keys.
  * Cache hit and miss events must be tracked programmatically and logged into `SearchDebugTracker` to monitor hit rate efficiency.

### [DAT-003] Repository Pattern & Data Access Isolation
Direct raw database querying or direct coupling of SQLAlchemy models within routers and services is strictly prohibited.
* **Requirements:**
  * All database operations must be isolated behind independent Repository classes or Database Access services (e.g., `HistoryRepository`, `UserRepository`, `WishlistRepository`).
  * The repository pattern ensures that changes to the database schemas do not bubble up and disrupt core business logic or presentation layers.
  * Session boundaries (`db: Session`) must be managed via dependencies injected into each repository.
