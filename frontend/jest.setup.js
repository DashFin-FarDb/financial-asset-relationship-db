// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

const createMatchMedia = ({ defaultMatches = false } = {}) =>
  jest.fn().mockImplementation((query) => {
    const listeners = new Set()

    const addChangeListener = (listener) => {
      if (typeof listener === 'function') listeners.add(listener)
    }

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

class MockIntersectionObserver {
  constructor (callback = () => {}, options = {}) {
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
