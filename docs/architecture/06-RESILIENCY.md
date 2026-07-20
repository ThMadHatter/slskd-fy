# System Resiliency & External Integrations

Track Portal communicates with multiple external services (including MusicBrainz, Slskd, and Navidrome). This document defines strict standards for API client resiliency, rate-limiting compliance, exception structures, and graceful degradation.

## Core Rules & Resiliency Standards

### [RSL-001] Respectful External API Integration & Rate Limiting
To prevent our self-hosted instances from getting blacklisted or blocked by external public registries like MusicBrainz, all outbound API clients must obey strict rate-limiting compliance.
* **Requirements:**
  * Define explicit rate limits (e.g., maximum 1 request per second for MusicBrainz calls) using global semaphores or rate-limiting token buckets.
  * Every request to an external third-party API must declare a customized, descriptive `User-Agent` header containing the application name, version, and a maintainer contact email.
  * Implement standard retry-and-backoff mechanisms (e.g., exponential backoff using `tenacity` or `httpx` retries) to handle transient 502/503/504 errors elegantly.

### [RSL-002] Domain-Specific Exception Hierarchies
Errors must be clearly categorized at boundary layers so that transient infrastructure faults can be isolated from logical or syntactic validation failures.
* **Requirements:**
  * Implement custom domain exceptions inheriting from a root `TrackPortalError` (e.g., `ExternalAPIError`, `NetworkTimeoutError`, `ValidationError`, `TaggingError`).
  * Raw HTTP exceptions or DB exceptions must be caught at service boundaries and re-raised as their corresponding domain-specific exceptions, preventing technical implementation details from leaking into routing or controller levels.

### [RSL-003] Graceful Degradation Mandates
The application must remain highly usable even when external third-party APIs or optional metadata endpoints suffer downtime.
* **Requirements:**
  * If MusicBrainz is unreachable or rate-limited, the search pipeline must gracefully fall back to executing manual Slskd queries directly using raw user input.
  * If Navidrome integration fails, track downloads and Beets tagging workflows must complete successfully, logging the Navidrome sync error as a non-fatal warning in the database audit log.
