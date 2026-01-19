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
  constructor () {}
  /**
   * Disconnects the observer instance (no-op placeholder for teardown if needed).
   * @returns {void}
   */
  disconnect () {
    // no-op placeholder for teardown if needed
  }

  /**
   * Placeholder method for observing a target; no operation in this mock.
   * @param {Element} target - The target element to observe
   * @returns {void}
   */
  observe (target) {
    // Intentionally left empty; placeholder method required by interface
  }

  /**
   * Returns any queued IntersectionObserverEntry records.
   * @returns {Array} Always returns an empty array in this mock.
   */
  takeRecords () {
    return []
  }

  /**
   * Stops observing a target element (no-op placeholder).
   * @param {Element} target - The target element to stop observing
   * @returns {void}
   */
  unobserve (target) {
    // no-op placeholder for unobserving targets
  }
}
