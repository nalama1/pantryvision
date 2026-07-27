# Contributing to PantryVision

Thanks for your interest in PantryVision. This started as a solo hackathon
project, and it is not currently seeking active contributors. That said,
suggestions, bug reports, and pull requests are welcome via GitHub Issues
and Pull Requests — just know that response times may vary since this is
maintained by a single person in their spare time.

## Reporting Bugs

If you find a bug, please open a [GitHub Issue](../../issues) with:

- A clear, descriptive title
- Steps to reproduce the problem
- What you expected to happen vs. what actually happened
- Screenshots or logs, if relevant (please redact any personal data or
  product images)
- Your environment (browser, OS) if it's a frontend issue

## Suggesting Features

Feature suggestions are also welcome as GitHub Issues. Please describe the
problem you're trying to solve, not just the solution you have in mind —
it helps evaluate whether it fits the project's scope (a lightweight,
serverless household inventory tool).

## Local Development Setup

See the [Getting Started](README.md#getting-started) section in the README
for prerequisites, environment variables, and instructions to run the
frontend and backend locally. This document won't duplicate those steps to
avoid them going out of sync.

## Code Style Conventions

### Backend (Python / AWS Lambda)

- Use `snake_case` for functions, variables, and file names
  (e.g., `get_product()`, `expiration_date`)
- Use `PascalCase` for class names
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints where practical
- Comments should explain the "why," not the "what," and be written in
  English

### Frontend (React / TypeScript)

- Use `camelCase` for functions and variables (e.g., `getProduct()`,
  `expirationDate`)
- Use `PascalCase` for component names and interfaces
- Comments should explain the "why," not the "what," and be written in
  English

### AWS Resources

- AWS resource names (S3 buckets, DynamoDB tables, Lambda functions) use
  `kebab-case`, all lowercase (e.g., `pantryvision-product-images`)

### Language

- **Code comments** are written in English, to stay consistent with the
  existing codebase.
- **Issues, pull requests, and discussions** can be written in **English or
  Spanish** — whichever is more comfortable for you. This project originated
  in a Spanish-speaking context, so Spanish contributions are just as
  welcome as English ones.

## Commit Conventions

- Keep commits small and focused on a single change
- Write descriptive commit messages in English
- Avoid bundling unrelated changes into a single commit

## Testing

- **Backend**: uses `pytest`, with property-based tests written using
  [Hypothesis](https://hypothesis.readthedocs.io/). Run tests from the
  relevant Lambda directory (e.g., `backend/extract-product-data`) with:

  ```bash
  pytest
  ```

- **Frontend**: uses [Vitest](https://vitest.dev/). Run tests from
  `/frontend` with:

  ```bash
  npm run test
  ```

New functionality should include tests covering the core logic and
important edge cases. Please don't submit PRs that reduce test coverage
without a good reason.

## Pull Requests

1. Fork the repository and create a branch for your change
2. Make sure existing tests pass and add new ones for your change
3. Open a pull request describing what changed and why
4. Be patient — as a solo-maintained project, reviews happen when time
   allows

## Security Issues

Please do **not** open a public issue for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for how to report them privately.
