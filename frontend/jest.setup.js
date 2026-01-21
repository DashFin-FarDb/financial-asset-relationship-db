// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

/**
 * Creates a mock matchMedia function for Jest.
 * @param {Object} [options] - Configuration options.
 * @param {boolean} [options.defaultMatches=false] - Initial match status.
 * @returns {jest.Mock} A Jest mock function simulating matchMedia.
 */
const createMatchMedia = ({ defaultMatches = false } = {}) =>
  jest.fn().mockImplementation((query) => {
    const listeners = new Set()

    /**
     * Adds a listener to be called when the media query changes.
     * @param {Function} listener - The change event listener.
     */
    const addChangeListener = (listener) => {
      if (typeof listener === 'function') listeners.add(listener)
    }

    /**
     * Removes a previously added change listener.
     * @param {Function} listener - The listener to remove.
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

/**
 * MockIntersectionObserver mimics the IntersectionObserver API for testing purposes.
 */
class MockIntersectionObserver {
  /**
   * Initializes the mock IntersectionObserver with a callback and options.
   *
   * @param {Function} callback - Function to be called when intersections occur.
   * @param {Object} options - Options to configure the observer.
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
  if (typeof window.matchMedia?.mockClear === 'function') {
    window.matchMedia.mockClear()
  }
})
