# Project Constitution

## 1. Code Quality Principles
- **Readability First**: Code must be written for humans to read. Use clear variable names and consistent formatting (PEP 8 for Python).
- **Modularity**: Functions and classes should have a single responsibility. Keep cyclomatic complexity low.
- **Documentation**: All public API methods, classes, and complex logic blocks must have docstrings.
- **Type Safety**: Use type hints (Python) to ensure static analysis can catch errors early.

## 2. Testing Standards
- **Test-Driven Development (TDD)**: Write tests before implementation details where possible.
- **Coverage**: Aim for high test coverage (>80%) on critical business logic and data processing pipelines.
- **Unit vs Integration**: Maintain a healthy pyramid of tests. Unit tests must be fast and isolated. Integration tests should verify system components (e.g., database, API) work together.
- **Data Integrity**: For data cleaning pipelines, implement "expectations" tests to validate data schemas and value ranges.

## 3. User Experience (UX) Consistency
- **Clarity**: Visualizations must be self-explanatory with clear legends, labels, and titles.
- **Responsiveness**: Dashboards and UIs should load quickly and handle interaction smoothly.
- **Error Feedback**: Provide clear, actionable error messages to users when something goes wrong (e.g., file upload failures).
- **Simplicity**: Avoid clutter. Focus on the key insights the user needs for HVAC analytics.

## 4. Performance Requirements
- **Data Processing**: ETL pipelines should optimize for memory usage (use generators/streaming or efficient libraries like Polars/Dask for large datasets).
- **Query Optimization**: SQL queries and API calls should be optimized to minimize latency.
- **Scalability**: The system should handle increasing data volumes without linear degradation in performance.
- **Resource Management**: Properly manage resources (close file handles, database connections) to prevent leaks.
