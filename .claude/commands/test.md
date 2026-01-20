# Run Tests

Run the pytest test suite with coverage reporting.

## Steps

1. Run the full test suite with coverage:
   ```bash
   pytest --cov=src/myriad --cov-report=term-missing -v
   ```

2. Analyze results:
   - If all tests pass: Report success and coverage percentage
   - If tests fail: List failed tests with their error messages
   - If coverage is below 80%: Note which files need more coverage

3. For failed tests, offer to:
   - Show the relevant source code
   - Suggest fixes
   - Write additional tests

## Quick Test Commands

Run specific test file:
```bash
pytest tests/test_<module>.py -v
```

Run tests matching pattern:
```bash
pytest -k "test_host" -v
```

Run with debug output:
```bash
pytest -v --tb=long
```

## Coverage Targets

- Overall: 80% minimum
- Services: 90% (business logic is critical)
- Routers: 70% (HTTP handling)
- Models: 60% (mostly data classes)
