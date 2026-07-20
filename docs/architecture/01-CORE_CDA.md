# Core Contract-Driven Architecture (CDA)

This document establishes the foundational design requirements and standards for the Contract-Driven Architecture (CDA) implemented across Track Portal. To support highly reliable, regression-free development ("vibe coding"), all modules must adhere strictly to these practices.

## Core Rules & Engineering Standards

### [CDA-001] Separation of Interfaces from Implementations
All core domain logic—including but not limited to search strategies, external API clients, database service layers, file organizers, and background execution loops—must be defined as formal Python interfaces *before* any implementation is written.
* **Requirements:**
  * Use either `abc.ABC` (with `@abc.abstractmethod`) or structural subtyping with `typing.Protocol`.
  * These abstract declarations must reside in an independent `contracts/` module or subdirectory under their respective domain packages (e.g., `app/contracts/` or `app/services/contracts/`).
  * Implementations must not expose public methods that are not declared in their parent contracts, ensuring code consumes only the interface contract.

### [CDA-002] Strict Data Boundary Validation
Under no circumstances should raw dictionaries or un-typed nested structures be allowed to cross boundary layers (e.g., from the API client into the service layer, or from service layer into the controllers/templates).
* **Requirements:**
  * All input and output boundaries must be defined, verified, and parsed using strict Pydantic schemas (v2 or higher).
  * Data must be strictly validated upon entry and serialization using Pydantic’s parsing mechanisms.
  * Explicit type hinting is mandatory for all functions, methods, parameters, and return types.

### [CDA-003] Strict Dependency Injection
Services must never instantiate their own dependencies or rely on global singleton imports inside functional code block bodies.
* **Requirements:**
  * All dependencies (e.g., database sessions, external API clients, storage pollers, config parameters) must be injected into the constructor (`__init__`) or passed explicitly as parameters to the executing functions.
  * The application configuration must use FastAPI’s dependency injection system (`Depends`) to resolve and supply instances of concrete classes bound to their respective Protocol/ABC definitions.
  * Under testing, dependency overrides must be explicitly cleared during test fixture teardown (`app.dependency_overrides.clear()`) to guarantee isolation.
