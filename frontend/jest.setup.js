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

/**
 * A mock implementation of IntersectionObserver for testing environments.
 * Tracks observed elements and allows manual triggering of callbacks.
 */
class MockIntersectionObserver {
  constructor (callback = () => undefined, options = {}) {
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

  /**
   * Triggers the IntersectionObserver callback with specified entries.
   * @param {IntersectionObserverEntry|IntersectionObserverEntry[]} entries - Single or array of entries to dispatch to the callback.
   * @returns {void}
   */
  triggerCallback (entries = []) {
    if (typeof this._callback !== 'function') return
    const normalizedEntries = Array.isArray(entries) ? entries : [entries]
    this._callback(normalizedEntries, this)
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
