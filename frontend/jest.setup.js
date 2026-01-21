// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

const createMatchMedia = ({ defaultMatches = false } = {}) =>
  jest.fn().mockImplementation((query) => {
    const listeners = new Set()
    const media = String(query ?? '')
    let matches = Boolean(defaultMatches)
    let onchange = null

    const notify = (event) => {
      listeners.forEach((listener) => listener(event))
      if (typeof onchange === 'function') onchange(event)
    }

    return {
      get matches () {
        return matches
      },
      media,
      get onchange () {
        return onchange
      },
      set onchange (nextOnChange) {
        onchange = nextOnChange
      },

      setMatches (newValue) {
        matches = Boolean(newValue)
        notify({ type: 'change', matches, media })
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
        notify(event)
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
  constructor (callback = () => undefined, options = {}) {
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

afterEach(() => {
  if (typeof window.matchMedia?.mockClear === 'function') {
    window.matchMedia.mockClear()
  }
})
