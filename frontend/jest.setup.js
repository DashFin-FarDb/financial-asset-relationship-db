// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

// Provide default environment values used throughout the app
process.env.NEXT_PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

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
class MockIntersectionObserver {
  constructor (callback = () => {}, options = {}) {
    this.callback = callback
    this.options = options
  }

  observe (target) {
    // no-op
  }

  unobserve (target) {
    // no-op
  }

  disconnect () {
    // no-op
  }

  takeRecords () {
    return []
  }
}

if (typeof globalThis !== 'undefined') {
  globalThis.IntersectionObserver = MockIntersectionObserver
}

// Basic scroll/resize mocks for components that rely on them
