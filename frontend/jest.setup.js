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
global.IntersectionObserver = class IntersectionObserver {
  constructor () {}
  disconnect () {}
  /**
   * Placeholder for observer method.
   *
   * This method is intentionally left empty and can be overridden to implement observer logic.
   * @returns {void}
   */
  observe () {
    // Intentionally empty: placeholder for observer
  }
    // Intentionally empty: placeholder for observer
  }

  /**
   * Retrieves all recorded entries.
   *
   * @returns {Array} An array of recorded entries.
   */
  static takeRecords () {
    return []
  }

  /**
   * Placeholder method to stop observing changes in a testing environment.
   *
   * @returns {void}
   */
  unobserve () {
    // No-op: placeholder for testing environment
  }
    // No-op: placeholder for testing environment
  }
}
