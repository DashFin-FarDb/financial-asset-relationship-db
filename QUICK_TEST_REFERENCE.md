# Quick Test Reference Guide

## Running Tests

### Basic Commands
```bash
cd frontend && npm test                    # Run all tests
cd frontend && npm test -- --coverage      # With coverage
cd frontend && npm test -- --watch         # Watch mode
```

### Run Specific Files
```bash
cd frontend && npm test -- MetricsDashboard.test.tsx      # Metrics component
cd frontend && npm test -- NetworkVisualization.test.tsx  # Visualization component
cd frontend && npm test -- page.test.tsx                  # Home page
cd frontend && npm test -- api.test.ts                    # API client
cd frontend && npm test -- integration/                   # Integration tests
```

### Run Specific Test Suites
```bash
cd frontend && npm test -- -t "Accessibility"             # Accessibility tests
cd frontend && npm test -- -t "Edge Cases"                # Edge case tests
cd frontend && npm test -- -t "Performance"               # Performance tests
cd frontend && npm test -- -t "Error Handling"            # Error handling tests
```

## Test Files

- **MetricsDashboard.test.tsx** - 221 lines, 23 tests
- **NetworkVisualization.test.tsx** - 315 lines, 20 tests
- **page.test.tsx** - 340 lines, 26 tests
- **api.test.ts** - 608 lines, 59 tests
- **component-integration.test.tsx** - 327 lines, 19 tests

## Coverage Areas

- **Accessibility** (8 tests) - WCAG, ARIA, semantic HTML
- **Edge Cases** (28 tests) - Boundaries, limits, invalid data
- **Error Handling** (15 tests) - Network, HTTP errors
- **Performance** (8 tests) - Large datasets, concurrency
- **Integration** (19 tests) - User journeys, data flow

## Documentation

- **COMPREHENSIVE_ADDITIONAL_TESTS_SUMMARY.md** - Detailed guide
- **TEST_GENERATION_COMPREHENSIVE_FINAL_SUMMARY.md** - Executive summary
- **QUICK_TEST_REFERENCE.md** - This file

## Quick Tips

1. Run before committing: `cd frontend && npm test`
2. Check coverage: `cd frontend && npm test -- --coverage`
3. Debug single test: `cd frontend && npm test -- -t "test name"`
4. Verbose output: `cd frontend && npm test -- --verbose`

Happy Testing! 🚀
