// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'

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
global.IntersectionObserver = class IntersectionObserver {
  disconnect () {
    // Placeholder for cleanup; intentionally left empty
  }

  observe () {
    // No-op mock for ResizeObserver.observe()
  }

  takeRecords () {
    return []
  }

  unobserve () {
    // no-op: placeholder for compatibility in Jest testing environment
  }
}
