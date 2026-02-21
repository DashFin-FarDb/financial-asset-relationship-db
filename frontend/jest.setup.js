// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

/**
 * Creates a mock matchMedia function for testing.
 * @param {Object} [options] Configuration options.
 * @param {boolean} [options.defaultMatches=false] Initial matches value.
 * @returns {function(string): object} Factory producing MediaQueryList mocks.
 */
const createMatchMedia = ({ defaultMatches = false } = {}) => {
  const listeners = new Set()
  let matches = Boolean(defaultMatches)

  /**
   * Factory function to create a mock MediaQueryList.
   * @param {string} query Media query string.
   * @returns {object} Mock MediaQueryList with addListener, removeListener, and setMatches.
   */
  const mqlFactory = (query) => {
    const media = String(query ?? '')

    const mql = {
      get matches () {
        return matches
      },
      media,
      onchange: null,

      setMatches (newValue) {
        matches = Boolean(newValue)
        const event = { type: 'change', matches, media }

        setTimeout(() => {
          listeners.forEach((listener) => listener(event))
          if (typeof mql.onchange === 'function') {
            mql.onchange(event)
          }
        }, 0)
      },

      addListener: jest.fn((listener) => {
        if (typeof listener === 'function') listeners.add(listener)
      }),
      removeListener: jest.fn((listener) => {
        listeners.delete(listener)
      }),

      addEventListener: jest.fn((eventName, listener) => {
        if (eventName === 'change' && typeof listener === 'function') {
          listeners.add(listener)
        }
      }),
      removeEventListener: jest.fn((eventName, listener) => {
        if (eventName === 'change') listeners.delete(listener)
      }),

      dispatchEvent: jest.fn((event) => {
        listeners.forEach((listener) => listener(event))
        if (typeof mql.onchange === 'function') {
          mql.onchange(event)
        }
        return true
      })
    }

    return mql
  }

  const mockFn = jest.fn(mqlFactory)

  mockFn.clearListeners = () => listeners.clear()

  return mockFn
}

Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  writable: true,
  value: createMatchMedia()
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

Object.defineProperty(window, 'IntersectionObserver', {
  configurable: true,
  writable: true,
  value: MockIntersectionObserver
})

Object.defineProperty(global, 'IntersectionObserver', {
  configurable: true,
  writable: true,
  value: MockIntersectionObserver
})

afterEach(() => {
  window.matchMedia = createMatchMedia()
})
