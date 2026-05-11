# procurement-agent UI

Front-end for the procurement agent. Built with Next.js 16, React 19,
TypeScript, and Tailwind CSS v4.

The UI is a single-page client app: a sortable list of purchase requests
on the left, a detail pane on the right showing the agent's assessment
timeline plus an inline override form, a slide-over panel for creating new
requests, and tabs for the supporting Policies and Vendors data.

## Architecture

```
src/
├── app/
│   ├── layout.tsx       Root layout, fonts, metadata.
│   ├── page.tsx         Top-level client component — tab routing + data fetch.
│   └── globals.css      Tailwind v4 import + CSS variables.
├── components/
│   ├── TopNav.tsx           Tab strip: Requests / Policies / Vendors.
│   ├── RequestList.tsx      Sidebar list, sort by amount/urgency/status/dates.
│   ├── RequestDetail.tsx    Right pane with assessment timeline + review.
│   ├── OverrideForm.tsx     Inline reviewer-decision form.
│   ├── NewRequestForm.tsx   Create-request form (rendered in SlideOver).
│   ├── SlideOver.tsx        Right-edge slide-out panel.
│   ├── PoliciesView.tsx     Policies grid.
│   └── VendorsView.tsx      Vendors grouped by status.
└── lib/
    ├── api.ts               Typed fetch wrapper around the agent's HTTP API.
    └── types.ts             Domain types — must stay in sync with agent models.
```

`src/lib/types.ts` mirrors `procurement-agent/src/models.py`. When the
agent's Pydantic models change, update both files in lockstep.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the procurement agent. |

## Commands

```bash
npm install         # install deps
npm run dev         # dev server on http://localhost:3000
npm run build       # production build
npm run start       # serve production build
npm run lint        # eslint
npm test            # run the vitest suite once
npm run test:watch  # vitest in watch mode
```

From the repo root, `npm run dev` launches both the agent (port 8000) and
the UI (port 3000) together.

## Testing

Tests live next to the code under `__tests__/`. The suite uses
[Vitest](https://vitest.dev/) + [@testing-library/react](https://testing-library.com/).

- `src/lib/__tests__/api.test.ts` — fetch wrapper contract: URLs, payloads,
  error paths.
- `src/components/__tests__/RequestList.test.tsx` — sort logic and click
  handling.
- `src/components/__tests__/OverrideForm.test.tsx` — reviewer submission
  shape including the derived `override` flag.

## Note on Next.js 16

This project pins Next.js 16, which has breaking changes vs older
versions. Read `node_modules/next/dist/docs/01-app/` before relying on
training-data knowledge of the API surface.
