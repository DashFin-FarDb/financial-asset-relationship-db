// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;


console.error = (...args) => {
  // Keep stack traces available while preventing noisy test output
  const message = args[0]?.toString() || ''
  if (message.includes('some-pattern-to-ignore')) {
    return
  }
// Provide default environment values used throughout the app
process.env.NEXT_PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

// Mock react-plotly.js to avoid heavy rendering in tests

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock IntersectionObserver
globalThis.IntersectionObserver = MockIntersectionObserver
class MockIntersectionObserver {
  constructor(callback = () => {}, options = {}) {
    this.callback = callback
    this.options = options
  }

  observe(target, options) {
    // no-op
  }

  unobserve(target) {
    // no-op
  }

  disconnect() {
    // no-op
  }

  takeRecords() {
    return []
  }
}

if (typeof globalThis !== 'undefined') {
  globalThis.IntersectionObserver = MockIntersectionObserver
}

// Basic scroll/resize mocks for components that rely on them
window.scrollTo = jest.fn()
window.resizeTo = jest.fn()
