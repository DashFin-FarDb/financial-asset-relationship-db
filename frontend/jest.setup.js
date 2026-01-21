// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

/**
 * Mock implementation of window.matchMedia.
 *
 * Required for components that rely on CSS media queries
 * (e.g. responsive layouts, MUI, Chakra, styled-components).
 */
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,

    // Legacy API (still used by some libraries)
    addListener: jest.fn(),
    removeListener: jest.fn(),

    // Modern API
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn()
  }))
})

/**
 * Mock implementation of IntersectionObserver.
 *
 * Used by components that rely on visibility detection
 * (e.g. lazy loading, infinite scroll, animations).
 */
class MockIntersectionObserver {
  constructor () {
    // No state required for test environment
  }

  /**
   * Start observing a target element.
   * No-op in test environment.
   */
  observe () {
    // Intentionally empty
  }

  /**
   * Stop observing a target element.
   * No-op in test environment.
   */
  unobserve () {
    // Intentionally empty
  }

  /**
   * Disconnect the observer.
   * No-op in test environment.
   */
  disconnect () {
    // Intentionally empty
  }

  /**
   * Retrieve queued intersection records.
   * Always empty in mocked environment.
   *
   * @returns {Array}
   */
  takeRecords () {
    return []
  }
}

// Attach mock to global scope
global.IntersectionObserver = MockIntersectionObserver
