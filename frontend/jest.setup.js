// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

const createMatchMedia = ({ defaultMatches = false } = {}) => {
  const listeners = new Set()
  let matches = Boolean(defaultMatches)

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
