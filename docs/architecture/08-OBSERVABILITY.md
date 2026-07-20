# System Observability & Tracing

To support deep troubleshooting and robust metrics analysis, this document establishes strict standards for structured log output, distributed tracing, and execution tracking.

## Core Rules & Observability Standards

### [OBS-001] Structured Telemetry Outputs
The system must generate structured logs separating human-readable diagnostics from machine-parseable telemetry metadata.
* **Requirements:**
  * Standardize log outputs to support a structured format (such as structured JSON logging) in production.
  * Telemetry metadata (e.g., query response times, cache hit/miss status, packet sizes) must be logged as key-value properties distinct from the informational message block.

### [OBS-002] End-to-End Correlation/Context ID Tracking
To trace search query execution flows and background behaviors, every incoming request must be associated with a unique identifier.
* **Requirements:**
  * Generate a unique Correlation/Context ID (e.g., UUIDv4) for every HTTP request or scheduled task.
  * Inject this Correlation ID into the logging context, propagating it across internal boundaries—specifically through the SearchProvider, the Progressive/Fallback Loop steps, and outbound Slskd API clients.

### [OBS-003] Explicit Logging Level Boundaries
To avoid diagnostic noise and maintain clean log pipelines, clear guidelines govern logging levels.
* **Requirements:**
  * **DEBUG:** Verbose execution tracing, raw payload values, database transaction starts, or transient cache lookups. Only enabled in development/debug modes.
  * **INFO:** Signifies standard system lifecycle transitions, successful user actions (logins, imports, enqueues), and background poller executions.
  * **WARNING:** Recoverable issues, slow API queries, rate-limit thresholds reached, or non-fatal synchronizations (e.g., Navidrome offline).
  * **ERROR:** Unrecoverable or critical failures requiring manual intervention, such as disk write failures, database corruptions, or complete Slskd service down times.
