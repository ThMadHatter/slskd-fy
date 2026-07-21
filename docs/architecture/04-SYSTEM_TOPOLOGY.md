# System Topology & Infrastructure Separation

To prevent dependency bloat and guarantee operational isolation, Track Portal is deployed via a multi-container architecture. This document defines the exact boundaries, communication vectors, and separation of concerns across the stack's primary nodes.

```
       +-------------------------------------------------------+
       |                     Docker Host                       |
       |                                                       |
       |   +------------------+         +------------------+   |
       |   |      Node A      |         |      Node B      |   |
       |   |   Track Portal   | <=====> |   Slskd Daemon   |   |
       |   |    (Web App)     |  HTTP   |  (P2P Networks)  |   |
       |   +------------------+         +------------------+   |
       |            |                             |            |
       |            | Read/Write                  | Writes     |
       |            | File Moves                  | Downloads  |
       |            v                             v            |
       |     +-------------------------------------------+     |
       |     |               Shared Volume               |     |
       |     |           (/mnt/music/Downloads)          |     |
       |     +-------------------------------------------+     |
       |                            ^                          |
       |                            | Monitors Downloads       |
       |                            | Trigger Tag & Import     |
       |                  +-------------------+                |
       |                  |      Node C       |                |
       |                  |   Beets Daemon    |                |
       |                  +-------------------+                |
       +-------------------------------------------------------+
```

## System Topology Standards

### [SYS-001] Node A: The Track Portal WebApp
* **Role:** Acts as the primary user-facing interface, background coordinator, and administrative orchestration engine.
* **Responsibilities:**
  * Serves the HTML frontend utilizing Jinja2 templates, HTMX, and Tailwind CSS.
  * Handles security controls including authentication, cookie-based session management, and CSRF token validations.
  * Manages search routing, query-strategy fallback execution, local SQLite caching, and Navidrome synchronization.
  * Issues programmatic REST instructions via HTTP to the Slskd API for transfer queuing and monitoring.
  * Coordinates background polling to monitor completed files on the shared storage volume.

### [SYS-002] Node B: The Slskd Daemon
* **Role:** Manages dedicated peer-to-peer (P2P) networking on the Soulseek network.
* **Responsibilities:**
  * Establishes direct connections to peers, handles user searches, queues transfers, and downloads incoming audio streams.
  * Exposes a robust REST API (protected via API tokens) consumed by Node A.
  * Writes incoming temporary and completed files directly into a specific subdirectory within the shared host-mounted storage volume (`/downloads` inside container, pointing to `/mnt/music/Downloads/slskd` on host).

### [SYS-003] Node C: Beets Integration & Isolation
* **Role:** Handles metadata normalization, automatic tag writing, directory organization, and final library placement.
* **Responsibilities:**
  * Remains entirely decoupled from Lidarr/Soularr workflows.
  * Operates as a background process or container that interacts with the download directory on the shared volume.
  * Triggers via filesystem events (e.g. `inotify`), daemon execution loops, or webhooks.
  * Automatically imports files non-interactively (`beet import -q -s` for singles, standard mode for albums).
  * Writes tags, renames files consistently, updates library paths, and triggers a rescan event on the indexer (e.g., Navidrome).
