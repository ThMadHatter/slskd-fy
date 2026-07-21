# Configuration Management

To ensure reliable, typed, and predictable environments across all deployment nodes, this document establishes strict rules for configuration bootstrapping, parsing, and injection.

## Core Rules & Configuration Standards

### [CFG-001] Strict Startup Configuration Validation
All environment variables, settings, and external API endpoint configurations must be validated eagerly at application boot time.
* **Requirements:**
  * Define configuration parameters using a structured model (e.g., `Settings` subclassing Pydantic's `BaseSettings` or `pydantic-settings`).
  * Any validation failure (e.g., missing keys, invalid data types, malformed URLs) must raise an immediate, informative error that prevents application startup.

### [CFG-002] Elimination of Raw Environment Access
No portion of the core business logic, services, routing handlers, or background loops may directly retrieve configuration values using raw OS-level environmental queries.
* **Requirements:**
  * Raw commands like `os.environ.get()` or `os.getenv()` are strictly prohibited outside the configuration module itself.
  * The parsed configuration object must be injected as a typed dependency (e.g., passing a `Settings` instance into constructors or using FastAPI's dependency injection system).

### [CFG-003] Query Strategy and Toggle Validation
Configurable execution parameters—specifically search strictness strategy profiles—must be strictly enumerated, parsed, and validated.
* **Requirements:**
  * Supported values for search execution mode strategies must be validated against a formal string enum class (e.g., `STRICT`, `BALANCED`, `AGGRESSIVE`).
  * Feature toggles and performance weights must be strongly typed (e.g., as booleans, integers, or strictly defined lists of strings) and parsed correctly from `.env` or system environment configurations.
