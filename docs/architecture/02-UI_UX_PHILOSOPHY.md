# UI/UX Philosophy & Mandates

Track Portal is built to satisfy a "Frictionless UX" aesthetic, minimizing the complexity of music discovery and download actions. This document outlines the explicit guidelines for UI design, caching strategies, and automated selection decisions.

## Core Rules & Design Standards

### [UX-001] The Frictionless UX Mandate
The search and download lifecycle must be optimized to require the absolute minimum number of clicks.
* **Requirements:**
  * The landing homepage must double as the primary search hub. There must be no unnecessary dashboard or telemetry wall blocking the user on initial load.
  * Direct downloads should be triggers via a single-click interactive component (e.g., HTMX triggers `[ Download ]`).
  * Progressive or lazy-loading (via HTMX `/search/enrich-row` endpoints) must be utilized for cache-miss metadata, ensuring fast initial page paint while extra calculations are run asynchronously.

### [UX-002] Zero-State Caching
Metadata searches, entity lookups, and autocomplete queries must be cached persistently to prevent rate limits and ensure instant retrieval times.
* **Requirements:**
  * Implement an active caching layer (`cache_entries` SQLite DB or similar Redis configuration).
  * Fast API lookups should hit local DB/caching queries first, recording metrics for hit/miss ratios to track optimization effectiveness.
  * Autocomplete search terms must use lightweight database indexes and prefix wildcard logic (e.g., `artist:({query}*)`) to support fast responsive UI dropdowns as the user types.

### [UX-003] Smart Auto-Selection
Complexity must be hidden from the user unless specifically requested. The application must feature an automated scoring and ranking system.
* **Requirements:**
  * File and peer candidate lists returned from Slskd must be programmatically evaluated, scored, and auto-sorted based on format/bitrate preferences (FLAC, 320kbps MP3s), shortest transfer queue status, and historical upload speeds.
  * If the user triggers a basic download request, the orchestrator must autonomously route the download to the absolute best candidate without displaying a manual search-result picker.
  * An "Advanced Mode" toggle can be enabled by advanced users to expose underlying technical raw attributes, diagnostics, or manual peer choices.

### [UX-004] Structural Album and UI Groupings
When performing searches targeting whole releases/albums rather than single tracks, results must be visually and structurally grouped to make the directory structure clean.
* **Requirements:**
  * Group results logically by their folder path structures.
  * Enable a one-click directory download option so an entire album can be enqueued to Slskd in a single interaction.
  * File names should be enriched and cleaned using parsers that strip scene/bracket/issue noise before displaying them in UI tables.
