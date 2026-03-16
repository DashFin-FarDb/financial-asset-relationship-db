// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

// Provide default environment values used throughout the app so tests
// do not fail due to a missing NEXT_PUBLIC_API_URL/NEXT_PUBLIC_API_BASE_URL.
const defaultApiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'

process.env.NEXT_PUBLIC_API_URL = defaultApiBaseUrl
process.env.NEXT_PUBLIC_API_BASE_URL = defaultApiBaseUrl

/**
 * Invoke all registered MediaQueryList listeners and onchange callback.
 * @param {Set<Function>} listeners Registered listeners.
 * @param {object} event Media query change event payload.
 * @param {Function|null} onchange Onchange callback.
 */
const emitMediaQueryChange = (listeners, event, onchange) => {
  for (const listener of listeners) {
    listener(event)
  }
  if (typeof onchange === 'function') {
    onchange(event)
  }
}

/**
 * Add listener only if it is callable.
 * @param {Set<Function>} listeners Registered listeners.
 * @param {unknown} listener Candidate listener.
 */
const addListenerIfFunction = (listeners, listener) => {
  if (typeof listener === 'function') listeners.add(listener)
}

/**
 * Add event listener only for MediaQueryList "change" events.
 * @param {Set<Function>} listeners Registered listeners.
 * @param {string} eventName Event name.
 * @param {unknown} listener Candidate listener.
 */
const addChangeEventListener = (listeners, eventName, listener) => {
  if (eventName === 'change' && typeof listener === 'function') {
    listeners.add(listener)
  }
}

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
        const notifyListeners = () =>
          emitMediaQueryChange(listeners, event, mql.onchange)

        setTimeout(notifyListeners, 0)
      },

      addListener: jest.fn((listener) =>
        addListenerIfFunction(listeners, listener)
      ),
      removeListener: jest.fn((listener) => {
        listeners.delete(listener)
      }),

      addEventListener: jest.fn((eventName, listener) =>
        addChangeEventListener(listeners, eventName, listener)
      ),
      removeEventListener: jest.fn((eventName, listener) => {
        if (eventName === 'change') listeners.delete(listener)
      }),

      dispatchEvent: jest.fn((event) => {
        emitMediaQueryChange(listeners, event, mql.onchange)
        return true
      })
    }

    return mql
  }

  const mockFn = jest.fn(mqlFactory)

  mockFn.clearListeners = () => listeners.clear()

  return mockFn
}

Object.defineProperty(globalThis, 'matchMedia', {
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

Object.defineProperty(globalThis, 'IntersectionObserver', {
  configurable: true,
  writable: true,
  value: MockIntersectionObserver
})

afterEach(() => {
  globalThis.matchMedia = createMatchMedia()
})
