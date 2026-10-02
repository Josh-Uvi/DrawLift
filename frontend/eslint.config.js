const typescriptParser = require("@typescript-eslint/parser");
const typescriptPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = [
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
        project: "./tsconfig.json", // Assuming a tsconfig.json exists
      },
    },
    plugins: {
      "@typescript-eslint": typescriptPlugin,
    },
    rules: {
      ...typescriptPlugin.configs.recommended.rules,
      // Add any specific rules or overrides here
    },
  },
  {
    files: ["**/*.js"], // For plain JavaScript files
    languageOptions: {
      parserOptions: {
        ecmaVersion: 2021,
        sourceType: "module",
      },
    },
    rules: {
      // Basic JS rules
    },
  },
];
