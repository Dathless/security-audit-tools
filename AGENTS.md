# Repository Guidelines

## Project Structure & Module Organization

`backend/` contains the FastAPI app: `api/` defines endpoints and WebSockets, `core/` runs scans and discovers modules, `storage/` holds persistence, and `modules/` contains scanners. Backend tests live in `backend/tests/` and module-local `tests/`. `frontend/src/` contains the React app, shared `core/`, reusable `design-system/`, and feature folders under `modules/`; static assets are in `frontend/public/`. `docs/` holds design and test notes. Add a backend module through `manifest.py` and `ScannerBase`; add a frontend module through `manifest.ts` and a page. Both registries discover modules automatically.

## Build, Test, and Development Commands

From the repository root, create a Python environment and run `pip install -r requirements.txt`. Run the API with `cd backend` then `uvicorn main:app --host 127.0.0.1 --port 8000`. In another terminal, use `cd frontend`, `pnpm install`, and `pnpm dev` for the Vite app. Run `pnpm lint` for ESLint and `pnpm build` for TypeScript checking and a production bundle.

## Coding Style & Naming Conventions

Follow nearby code: Python uses four-space indentation, `snake_case` functions and files, and `PascalCase` classes. TypeScript/React uses two-space indentation, `PascalCase` components and types, and camelCase functions. Keep module IDs and routes in kebab-case, for example `port-scanner`. Reuse `ScannerBase`, API envelopes, and design-system components before adding new abstractions. Do not introduce a formatter or dependency for a small change.

## Testing Guidelines

From `backend/`, run `pytest` for unit and API tests. Name tests `test_*.py`; mock OS and network observations so tests do not depend on the host machine. Selenium UI tests are opt-in: run `pytest tests/test_selenium_*.py --selenium`. Add focused tests for new scan rules, API behavior, and failure handling. Run frontend lint and build when changing UI or types.

## Commit & Pull Request Guidelines

Recent commits use short prefixes such as `docs:` and `chore:`; use an imperative, scoped subject, for example `feat: add firewall profile checks`. Keep unrelated working-tree changes out of the commit. PRs should explain behavior, relevant checks, and any security or compatibility impact; attach screenshots for visible UI changes and link an issue when one exists.

## Security & Configuration

Keep `backend/config.yaml`, local tokens, frontend `.env` files, and scan databases out of commits. Preserve localhost binding and `X-Local-Token` checks. The repository ignores `docs/`; explicitly stage only documentation files intended for a commit. If a `.codegraph/` index exists, query it before text search when locating code.
