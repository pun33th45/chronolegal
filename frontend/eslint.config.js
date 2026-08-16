import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

// ESLint 9 requires this flat-config file — package.json already declares
// @eslint/js, typescript-eslint, and eslint-plugin-react-hooks as
// devDependencies, but no config file existed anywhere in the repo, so
// `npm run lint` failed to even start (silently masked by CI's
// continue-on-error). This wires up exactly those three already-declared
// tools, nothing new.
export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      // TypeScript's own compiler (see `npm run type-check`) already
      // catches undefined references more accurately than ESLint's scope
      // analysis, which doesn't know about browser/DOM globals without an
      // extra `globals` package this project doesn't otherwise need.
      'no-undef': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
)
