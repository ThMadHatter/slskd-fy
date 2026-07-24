# UI / Implementation Gap Analysis

## Overview

This document presents a comprehensive audit and gap analysis of the Track Portal frontend (redesigned with Google Stitch) against the FastAPI backend services and slskd/Beets integration.

The purpose of this analysis is to map visible UI components, identify fully functioning features, highlight partially implemented logic, detect broken flows, and document purely decorative placeholders. This analysis forms the technical roadmap for connecting the high-fidelity UI to real, production-ready system functionality.

---

## 1. Executive Summary

- **Core Search & Downloading (P0):** The primary structured search flow and individual/bulk download triggers are **fully functional** and connected to the backend. Accordion album grouping and client-side refinement filters are implemented on the frontend.
- **Transfers & Download Management (P0/P1):** The **Downloads** tab is currently a **100% placeholder** utilizing a local, hardcoded frontend Zustand store. It is not connected to any backend transfer APIs or background download pollers.
- **Explore & Discoverability (P1/P2):** The **Explore** view is entirely static mock data on the frontend. No real "Trending", "Similar Artists", or "Global Additions" backend data exists.
- **System Settings & Integrations (P1):** The **Settings** view is fully disconnected from the backend. Saving configuration parameters only modifies local frontend Zustand state and does not persist to backend settings or environmental databases.

---

## 2. Component Audits

### Component: Structured Query Form (HomeView)
- **Current State:** PARTIALLY_IMPLEMENTED
- **Backend Implementation Status:** IMPLEMENTED
  - Autocomplete queries, search execution orchestrator, and progressive fallbacks are fully supported.
- **Frontend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Inputs for Artist Name and Track/Album are fully connected to autocomplete endpoints and execute searches.
  - However, the **Strategy Selector** (Mode A, Mode B, Mode C) is a placeholder-only element. The frontend search payload to `/api/search` completely omits the selected `searchMode` or `mode`, resulting in the backend defaulting to Mode A for all requests.
- **User Impact:** High. Users can search and find tracks, but they cannot switch search strategies (e.g., to exact quotes or power-user Lucene fields).
- **Technical Complexity:** Low.
- **Recommended Priority:** P0

---

### Component: Free Text Keywords (HomeView)
- **Current State:** BROKEN
- **Backend Implementation Status:** PARTIALLY_IMPLEMENTED
  - The progressive search executor and query permutation generator can handle search keywords.
- **Frontend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Form UI is fully visible and captures text inputs.
- **User Impact:** High. Searching via Free Text Keywords fails because the backend Pydantic validation schema `SearchQuery` strictly enforces `min_length=1` for both `artist` and `track` fields. Because the frontend passes an empty string for the artist field in Free Text mode, it triggers an HTTP 422 Unprocessable Entity error.
- **Technical Complexity:** Low.
- **Recommended Priority:** P0

---

### Component: Search Results Table (SearchResultsView)
- **Current State:** PARTIALLY_IMPLEMENTED
- **Backend Implementation Status:** IMPLEMENTED
  - Metadata parser, Beets enrichment score matching, duplicate check flags, and download enqueuing are fully implemented.
- **Frontend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Sorting, accordion album grouping, formatting badges, and item selection are implemented.
  - Basic individual download triggers and bulk download triggers successfully call `/api/download`.
  - However, Beets metadata confidence flags and search diagnostics/scoring reasons (e.g., positive/negative scoring contributions) are not rendered to the user.
- **User Impact:** Medium. Results are displayed and downloadable, but the "why" behind confidence ranking and metadata matching remains invisible.
- **Technical Complexity:** Low to Medium.
- **Recommended Priority:** P1

---

### Component: Compare Bitrates Action (SearchResultsView Bulk Bar)
- **Current State:** PLACEHOLDER
- **Backend Implementation Status:** NOT_IMPLEMENTED
- **Frontend Implementation Status:** PLACEHOLDER
  - Button is visible in the bulk action bar when rows are selected, but only triggers a static toast message.
- **User Impact:** Low. Users cannot automatically compare bitrates among selected items.
- **Technical Complexity:** Low.
- **Recommended Priority:** P2

---

### Component: Refine Search Sidebar (SearchResultsView Sidebar)
- **Current State:** IMPLEMENTED
- **Backend Implementation Status:** NOT_IMPLEMENTED (By design)
  - Raw client-side filtering avoids redundant backend requests to the slskd API.
- **Frontend Implementation Status:** IMPLEMENTED
  - Formats, bitrate preferences, maximum file size, queue length, and user filters are fully functional using reactive React `useMemo` states on search results.
- **User Impact:** High positive impact. Users can filter high-volume search responses instantly.
- **Technical Complexity:** Low.
- **Recommended Priority:** P2 (Maintenance)

---

### Component: Transfer Queue (DownloadsView)
- **Current State:** PLACEHOLDER
- **Backend Implementation Status:** IMPLEMENTED
  - FastAPI contains endpoints for background polling and `SlskdClient` supports `GET /api/v0/transfers/downloads` to retrieve real-time download items.
- **Frontend Implementation Status:** PLACEHOLDER
  - UI is completely populated by 6 static hardcoded mockup transfers.
  - Toolbar buttons (Pause All, Resume All, Clear Completed) and row actions (Pause, Resume, Cancel, Retry, Open Folder) only update frontend mock state variables. They are completely isolated from real-world slskd transfer queues.
- **User Impact:** Critical. Users have zero real-time visibility into their downloads, speeds, or failure states.
- **Technical Complexity:** Medium.
- **Recommended Priority:** P0

---

### Component: Connection Status Widget (SideNavBar Footer)
- **Current State:** PLACEHOLDER
- **Backend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Backend has a `/health` database and API connection checker.
- **Frontend Implementation Status:** PLACEHOLDER
  - "slskd connected" status is static green pulsing text with hardcoded active download counts.
- **User Impact:** Medium. Displays a false positive status even if the slskd daemon is offline.
- **Technical Complexity:** Low.
- **Recommended Priority:** P1

---

### Component: Settings Panel (SettingsView)
- **Current State:** PLACEHOLDER
- **Backend Implementation Status:** NOT_IMPLEMENTED
  - No read/write database configurations or dynamic environment adjustment endpoints are present for system configs.
- **Frontend Implementation Status:** PLACEHOLDER
  - Form fields save to local Zustand storage only. Page reloads and server restarts drop modifications.
- **User Impact:** High. Users cannot adjust api endpoints, key parameters, or thresholds through the GUI.
- **Technical Complexity:** Medium.
- **Recommended Priority:** P1

---

### Component: Explore View (ExploreView)
- **Current State:** PLACEHOLDER
- **Backend Implementation Status:** NOT_IMPLEMENTED
  - No database models or scrapers exist for trending albums, trending artists, similar artist graphs, or random collection picks.
- **Frontend Implementation Status:** PLACEHOLDER
  - Complete view consists of high-fidelity static cards. Clicking "Explore" redirects to search and starts a structured query but uses hardcoded inputs.
- **User Impact:** Low. It is secondary to core downloading mechanics.
- **Technical Complexity:** High.
- **Recommended Priority:** P2

---

### Component: TopBar Search / Command Palette (TopAppBar & CommandPalette)
- **Current State:** PARTIALLY_IMPLEMENTED
- **Backend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Basic static routing and mock endpoint benchmarks exist.
- **Frontend Implementation Status:** PARTIALLY_IMPLEMENTED
  - Global hotkeys (⌘K) trigger the command menu. Navigation commands work properly.
  - Action commands (Pause All, Clear Completed) only fire mock Zustand state mutations.
- **User Impact:** Medium. Good navigation tool, but cannot execute actual admin macros or background commands.
- **Technical Complexity:** Low.
- **Recommended Priority:** P2

---

## 3. Gap Details and Remediations

### Gap 1: Free Text Search Validation Error
- **Description:** Executing keywords search triggers an HTTP 422 Unprocessable Entity error.
- **Root Cause:** Backend contract validation schema `SearchQuery` in `app/contracts/schemas.py` requires both `artist` and `track` to have `min_length=1`. Free Text Keywords search submits an empty artist name.
- **Suggested Solution:**
  1. Modify `SearchQuery` constraints to allow either `artist` or `track` to be empty, as long as at least one parameter is supplied (e.g., using a model validator).
  2. Ensure the query generation engine properly formats raw text string structures.
- **Estimated Effort:** 2 Hours

---

### Gap 2: Disconnected Strategy Mode Selection
- **Description:** Clicking Mode A, B, or C strategy filters does not alter search behavior or query formatting.
- **Root Cause:** The frontend `fetch` request payload in `HomeView.tsx` neglects to map the `searchMode` from Zustand store into the POST body under `mode`.
- **Suggested Solution:**
  - Update `HomeView.tsx` search trigger body to:
    ```json
    {
      "artist": searchArtist,
      "track_or_album": searchTrack,
      "mode": searchMode
    }
    ```
- **Estimated Effort:** 1 Hour

---

### Gap 3: Disconnected Real-time Downloads
- **Description:** Downloads tab is decoupled from the active slskd transfers.
- **Root Cause:** Frontend store `downloadStore.ts` starts with static mocked objects and fails to poll any backend APIs.
- **Suggested Solution:**
  1. Add a backend controller endpoint `GET /api/transfers` which queries `SlskdClientContract.get_downloads()`.
  2. Configure frontend `downloadStore.ts` to execute recursive polling (e.g., via React Query or standard fetch intervals) to fetch and map slskd transfer states.
  3. Map action methods (Pause, Cancel, Resume) to active slskd client REST endpoints.
- **Estimated Effort:** 1.5 Days

---

### Gap 4: Disconnected System Configurations
- **Description:** Modifying Settings does not affect environment variables or backend configurations.
- **Root Cause:** Missing backend configuration endpoints (`GET /api/settings` and `POST /api/settings`) to dynamically load and write settings.
- **Suggested Solution:**
  1. Create a dynamic configuration model or database table in SQLAlchemy.
  2. Implement backend settings router endpoints to read/update settings.
  3. Update `SettingsView.tsx` to pull and persist state via standard API calls instead of frontend local storage.
- **Estimated Effort:** 1 Day

---

### Gap 5: Last.fm Pulsing Fake Sync
- **Description:** TopAppBar claims "Last.fm Sync Active" but no actual Last.fm sync exists.
- **Root Cause:** Decorative feature mockup added by design tools.
- **Suggested Solution:**
  - Remove the pulsing fake sync label from `TopAppBar.tsx`, or replace it with a genuine connection indicator mapping to Beets/slskd daemon status.
- **Estimated Effort:** 1 Hour

---

## 4. Prioritized Project Roadmap

The following defines the prioritized development roadmap to systematically resolve all implementation gaps.

### Phase 1: Core Flow Integrity (P0) - *Critical*
1. **Fix Free Text Query Validation (Gap 1):** Allow single-field query inputs on `SearchQuery` Pydantic model.
2. **Connect Search Strategies (Gap 2):** Include selected strategy mode in search API requests.
3. **Connect Real-time Transfers (Gap 3):** Bind the Downloads tab to actual background polling states. Enable cancel/pause actions.

### Phase 2: Metadata & Diagnostics (P1) - *High Value*
1. **Expose Scoring Explanations:** Display detailed positive/negative scoring contributions in a tooltip or custom badge in the results grid.
2. **Real Connection Metrics:** Replace static "slskd connected" and "Last.fm" labels with a real healthcheck polling status.
3. **Database Configuration Persistence (Gap 4):** Connect the Settings Panel to a persistent SQLite configurations database.

### Phase 3: Secondary Features & Polishing (P2/P3) - *Nice to Have & Cosmetic*
1. **Dynamic Explore Panel:** Construct a backend background worker to compile actual local search histories or catalog statistics to populate trending cards.
2. **Bulk Compare Bitrates:** Implement local client-side duplicate resolution tools or bitrate visualizer charts.
3. **Clean Up Decorative Elements (Gap 5):** Remove hardcoded elements, false indicators, and non-navigating buttons.
