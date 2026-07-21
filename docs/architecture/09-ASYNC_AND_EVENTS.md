# Asynchronous Operations & Event-Driven Boundaries

To ensure highly responsive interfaces and isolated automation pipelines, this document defines standards for real-time events, background loops, and multi-node notifications.

## Core Rules & Event Standards

### [EVT-001] Real-Time UI Synchronization
To prevent aggressive HTTP polling from client browsers, updates for active downloads, transfer speeds, and queue statuses must use real-time protocols.
* **Requirements:**
  * Define clear contracts for streaming updates to client-side UI wrappers (e.g., HTMX integration) utilizing either Server-Sent Events (SSE) or WebSockets.
  * Payloads sent over the wire must be modeled as structured Pydantic event schemas before serialization.

### [EVT-002] Multi-Node Automation Boundaries (Beets Webhooks)
Communication triggers between the WebApp (Node A), Slskd (Node B), and Beets (Node C) must use standardized, immutable payloads.
* **Requirements:**
  * Once a download has successfully completed, the WebApp must emit a standardized webhook event or message payload to trigger Node C (Beets).
  * The completion event schema must declare fields for: `download_id`, `original_filepath`, `format`, `source_peer`, and `monitored_item_type` (e.g., single vs album).

### [EVT-003] ASGI Event Loop Integrity
Background operations must not execute blocking, synchronous I/O operations directly within the ASGI/WSGI main runtime thread loop.
* **Requirements:**
  * Any blocking operations—including filesystem manipulations, tag writing using Mutagen, or network requests—must be executed using asynchronous wrappers (e.g., using `anyio.to_thread.run_sync` or running tasks on a separate executor).
  * Long-running background processes (like the download history poller) must yield execution regularly using `await asyncio.sleep(...)` to ensure the core thread can process incoming HTTP and WebSocket requests concurrently.
