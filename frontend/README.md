# NovaBank: web app

Angular 21 (standalone components, signals, zoneless) front end for the NovaBank API.

```bash
npm ci
npm start          # http://localhost:4200, proxies /api to the Django API on :8000
npm test           # unit tests (Vitest)
npm run build
```

Every element a test touches has a `data-testid`. See the repo's [LEARN.md](../LEARN.md), part 5.
