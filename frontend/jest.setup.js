// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn()
  }))
})

// Mock IntersectionObserver
/**
 * Mock IntersectionObserver class for testing environment.
 */
global.IntersectionObserver = class IntersectionObserver {
  /**
   * Constructs the mock IntersectionObserver.
   */
  /**
   * Disconnects the observer instance (no-op placeholder for teardown if needed).
   * @returns {void}
   */
  static disconnect () {
    // no-op placeholder for teardown if needed
  }

  /**
   * Placeholder method for observing a target; no operation in this mock.
   * @returns {void}
   */
  static observe (_target) {
    // Intentionally left empty; placeholder method required by interface
  }

  static unobserve (_target) {
    // Intentionally left empty; placeholder method required by interface
  }

  /**
   * Returns any queued IntersectionObserverEntry records.
   * @returns {Array} Always returns an empty array in this mock.
   */
  static takeRecords () {
    return []
  }
}
