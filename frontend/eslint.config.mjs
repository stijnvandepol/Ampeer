import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // eslint-config-next enables `no-unused-vars` with a severity and no
    // options, so the rule runs on its own defaults, and one of those defaults
    // is `ignoreRestSiblings: false`. That flags the binding in
    // `const { year: _dropped, ...without } = fixture`, which is the idiom for
    // building an object with one key left out: the binding exists so the rest
    // element can exclude it, and it is unused on purpose. Turning it on here
    // does not weaken the rule for anything else; a variable that is simply
    // never used is still reported, which
    // `tests/lint/unused-vars.test.ts` proves by running eslint over a source
    // that has one.
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { ignoreRestSiblings: true },
      ],
    },
  },
]);

export default eslintConfig;
