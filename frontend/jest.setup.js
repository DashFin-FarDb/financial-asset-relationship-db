// jest.setup.js
// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

/**
 * Creates a mock matchMedia function for Jest.
 * @param {Object} [options]
 * @param {boolean} [options.defaultMatches=false]
 * @returns {jest.Mock}
 */
const createMatchMedia = ({ defaultMatches = false } = {}) => {
  return jest.fn().mockImplementation((query) => {
    const listeners = new Set()
    let matches = Boolean(defaultMatches)
    const media = String(query ?? '')
    const mql = {
      get matches () {
        return matches
      },
      media,
      onchange: null,

      /** Set matches value and notify listeners */
      setMatches (newValue) {
        matches = Boolean(newValue)
        const event = { type: 'change', matches, media }
        listeners.forEach((listener) => listener(event))
        if (typeof mql.onchange === 'function') mql.onchange(event)
      },

      /** Deprecated listener methods */
      addListener: jest.fn((listener) => {
        if (typeof listener === 'function') listeners.add(listener)
      }),
      removeListener: jest.fn((listener) => {
        listeners.delete(listener)
      }),

      /** Standard event methods */
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
        if (typeof mql.onchange === 'function') mql.onchange(event)
        return true
      })
    }
    return mql
  })
}

// Define mock on window
Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  writable: true,
  value: createMatchMedia()
})

/**
 * MockIntersectionObserver simulates IntersectionObserver for Jest.
 */
class MockIntersectionObserver {
  /**
   * @param {Function} callback
   * @param {Object} options
   */
  constructor (
    callback = () => {
      /* no-op placeholder callback */
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
      if (element) this._elements.delete(element)
    })

    this.disconnect = jest.fn(() => {
      this._elements.clear()
    })

    this.takeRecords = jest.fn(() => [])
  }
}

// Assign to window and global
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

// Cleanup mocks after each test
afterEach(() => {
  if (typeof window.matchMedia?.mockClear === 'function') {
    window.matchMedia.mockClear()
  }
  if (
    typeof MockIntersectionObserver.prototype.observe?.mockClear === 'function'
  ) {
    MockIntersectionObserver.prototype.observe.mockClear()
  }
  if (
    typeof MockIntersectionObserver.prototype.unobserve?.mockClear ===
    'function'
  ) {
    MockIntersectionObserver.prototype.unobserve.mockClear()
  }
  if (
    typeof MockIntersectionObserver.prototype.disconnect?.mockClear ===
    'function'
  ) {
    MockIntersectionObserver.prototype.disconnect.mockClear()
  }
})
