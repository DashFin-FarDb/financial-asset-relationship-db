# API Library Tests

This directory contains comprehensive tests for the frontend API client library.

## Test Files

### api.test.ts (431 lines)
Original comprehensive tests for the API client covering:
- Client configuration
- All API methods (health, assets, relationships, metrics, visualization)
- Request parameter handling
- Response type validation
- Error handling

### api-axios-compatibility.test.ts (697 lines) ✨ NEW
Axios 1.13.2 compatibility and behavioral tests:
- Axios instance creation and configuration
- Request configuration (query params, URL encoding)
- Response handling (data extraction, headers)
- Error handling (AxiosError types, HTTP errors, timeouts)
- Content-Type handling
- URL handling (baseURL, paths)
- TypeScript type safety
- Backward compatibility with axios 1.6.0
- Edge cases (long URLs, concurrent requests)
- Interceptor compatibility
- Performance optimization

**60+ tests across 13 test suites**

### api-upgrade-integration.test.ts (397 lines) ✨ NEW
Integration tests for axios 1.13.2 upgrade:
- Production usage patterns
- Error recovery patterns
- Security improvements
- Breaking change detection
- Performance validation
- Environment configuration
- Testing tool compatibility
- Real-world edge cases

**40+ tests across 10 test suites**

## Running Tests

### Run all API tests
```bash
npm test -- __tests__/lib
```

### Run specific test files
```bash
# Original API tests
npm test -- api.test

# Axios compatibility tests
npm test -- api-axios-compatibility

# Upgrade integration tests
npm test -- api-upgrade-integration
```

### Run with coverage
```bash
npm run test:coverage -- __tests__/lib
```

## Test Coverage

These tests provide comprehensive coverage of:
- ✅ All API endpoints
- ✅ Request/response handling
- ✅ Error scenarios
- ✅ TypeScript type safety
- ✅ Axios 1.13.2 features
- ✅ Backward compatibility
- ✅ Security improvements
- ✅ Performance characteristics
- ✅ Production usage patterns

## Documentation

For detailed information about the axios upgrade tests:
- Quick Reference: `../../AXIOS_TESTS_QUICK_REFERENCE.md`
- Detailed Report: `../../AXIOS_UPGRADE_TEST_REPORT.md`
- Complete Summary: `../../TEST_GENERATION_SUMMARY_FINAL.md`

## Maintenance

When updating tests:
1. Keep tests synchronized with API changes
2. Update axios version assertions when upgrading
3. Add tests for new API methods
4. Validate TypeScript types on dependency updates
5. Run full test suite before committing

## Test Statistics

- **Total Test Files**: 3
- **Total Test Lines**: 1,525 lines
- **Total Test Cases**: 131+ tests
- **Test Suites**: 33+ describe blocks
