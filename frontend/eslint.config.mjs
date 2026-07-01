import js from '@eslint/js'
import globals from 'globals'
import tsParser from '@typescript-eslint/parser'
import reactPlugin from 'eslint-plugin-react'

export default [
  js.configs.recommended,
  {
    ignores: [
      'node_modules/',
      '.next/',
      'dist/',
      'build/',
      'coverage/',
      '__tests__/test-utils.test.ts',
      '__tests__/test-utils.ts'
    ]
  },
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      react: reactPlugin
    },
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        jest: 'readonly',
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        beforeAll: 'readonly',
        beforeEach: 'readonly',
        afterAll: 'readonly',
        afterEach: 'readonly'
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      }
    },
    rules: {
      'no-unused-vars': 'off',
      'no-undef': 'off',
      'react/react-in-jsx-scope': 'off'
    }
  }
]
