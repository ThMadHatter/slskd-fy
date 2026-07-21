# Quality Gates & Testing Standards

To maintain stable, robust, and regression-free operation, this document defines testing policies, boundary definitions, coverage targets, and specific verification criteria.

## Core Rules & Testing Standards

### [QG-001] Strict Testing Boundaries
We enforce a strict separation of concerns between unit testing layers and integration testing layers.
* **Requirements:**
  * **Unit Tests:** Must evaluate core domain and service logic by mocking external calls, databases, and dependencies. Unit tests must use mock objects implementing defined contracts. Network calls or raw disk writes are strictly prohibited in unit tests.
  * **Integration Tests:** Must evaluate actual system execution flows, HTTP communications (e.g., Slskd or Navidrome API mock responders), and database operations.

### [QG-002] Coverage for Search and Fallback Strategies
Automated search query optimization must be extensively validated, specifically the transition loops between different strictness modes.
* **Requirements:**
  * Testing suites must fully cover query generation mechanisms under all modes: Mode A (standard keywords), Mode B (exact quotes), and Mode C (prefixed Lucene fields).
  * The transition loop fallback logic (`STRICT` -> `BALANCED` -> `AGGRESSIVE`) must be covered with specific test cases asserting query broadening under zero-result conditions.
  * Telemetry trackers, such as `/admin/search-debug` statistics and strategy benchmark performance metrics, must be actively verified for correct behavior and non-regression.

### [QG-003] The Feature-Contract Rule
No feature is considered complete until it contains both a formal contract definition and tests verifying that contract.
* **Requirements:**
  * Any new service, utility, or logic route must be defined by an interface or Protocol schema.
  * Corresponding test suites must validate contract behavior, verifying expected outputs under valid parameters and exception handling on failure modes.
  * Developers must verify test execution using standard pytest commands:
    ```bash
    python -m pytest --cov=app --cov-report=term-missing
    ```
