// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

/**
 * Creates a mock implementation of window.matchMedia for testing.
 * @param {object} [options] - Configuration options.
 * @param {boolean} [options.defaultMatches=false] - The default match state.
 * @returns {jest.Mock} A jest mock function for matchMedia.
 */
const createMatchMedia = ({ defaultMatches = false } = {}) =>
  jest.fn().mockImplementation((query) => {
    const listeners = new Set()
    const intersectionObserverInstances = new Set()

    const addChangeListener = (listener) => {
      // In afterEach hook, consider also clearing listener sets by resetting the mock implementation.
      afterEach(() => {
        // Reset window.matchMedia to a fresh mock to clear all internal state
        window.matchMedia = createMatchMedia()
        intersectionObserverInstances.clear()
      })
    }

    /**
     * Removes a change listener from the listeners set.
     * @param {Function} listener - The listener function to remove.
     */
    const removeChangeListener = (listener) => {
      listeners.delete(listener)
    }

    return {
      matches: defaultMatches,
      media: String(query ?? ''),
      onchange: null,

      // Deprecated but still used in some libraries
      addListener: jest.fn(addChangeListener),
      removeListener: jest.fn(removeChangeListener),

      // Standard API
      addEventListener: jest.fn((eventName, listener) => {
        if (eventName === 'change') addChangeListener(listener)
      }),
      removeEventListener: jest.fn((eventName, listener) => {
        if (eventName === 'change') removeChangeListener(listener)
      }),

      dispatchEvent: jest.fn((event) => {
        listeners.forEach((listener) => listener(event))
        return true
      })
    }
  })

Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  writable: true,
  value: createMatchMedia()
})

const intersectionObserverInstances = new Set()

/**
 * MockIntersectionObserver simulates the browser's IntersectionObserver for testing.
 *
 * It provides jest.fn mocks for observe, unobserve, disconnect, and takeRecords,
 * and allows manual triggering of intersection entries.
 */
class MockIntersectionObserver {
  /**
   * Constructs a new MockIntersectionObserver.
   *
   * @param {Function} callback - Callback invoked with intersection entries.
   * @param {Object} [options={}] - IntersectionObserver options.
   */
  constructor (
    callback = () => {
      /* default no-op callback */
    },
    options = {}
  ) {
    this._callback = callback
    this._options = options
    this._elements = new Set()

    this.observe = jest.fn((element) => {
      if (element) this._elements.add(element)
    })

    this.unobserve = jest.fn((element) => {
      this._elements.delete(element)
    })

    this.disconnect = jest.fn(() => {
      this._elements.clear()
    })

    this.takeRecords = jest.fn(() => [])

    intersectionObserverInstances.add(this)
  }

  /**
   * Test helper: triggers the observer callback.
   *
   * @param {Array<Partial<IntersectionObserverEntry>>} entries
   */
  _trigger (entries = []) {
    this._callback(entries, this)
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

Object.defineProperty(global, '__mockIntersectionObservers', {
  configurable: true,
  get: () => Array.from(intersectionObserverInstances)
})

afterEach(() => {
  if (typeof window.matchMedia?.mockClear === 'function') {
    window.matchMedia.mockClear()
  }
  intersectionObserverInstances.clear()
})
