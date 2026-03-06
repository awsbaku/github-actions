# Plan: Hackathon Leaderboard Frontend

## Context

Backend is complete and deployed:
- Lambda Function URL: `https://d4a7fri5bf5sf6m6u433raysvi0nwhxb.lambda-url.eu-central-1.on.aws/`
- DynamoDB table: `awsbaku-infrastructure-org-hackathon-scores`
- Lambda writes `leaderboard.json` to S3 at `hackathon-leaderboard/leaderboard.json`
- CloudFront serves the existing React SPA with SPA fallback (403/404 -> index.html)
- OIDC role updated with `lambda:InvokeFunctionUrl`
- `evaluate-prs.yml` updated with leaderboard submission step

**This plan covers the frontend implementation only** -- adding a `/hackathon-leaderboard` route to the existing `awsbaku/public-frontend` React app.

## Existing Stack (public-frontend)

| Tool | Version | Purpose |
|------|---------|---------|
| React | 19.2.0 | UI framework |
| Vite | 7.3.1 | Bundler |
| TypeScript | ~5.9.3 | Type safety (strict mode) |
| Tailwind CSS | 4.2.1 | Styling (dark theme, CSS variables) |
| TanStack Query | 5.90.21 | Data fetching + caching |
| Framer Motion | 12.34.3 | Animations |
| react-router-dom | 7.13.1 | Client-side routing |
| lucide-react | 0.575.0 | Icons |
| Biome | 1.9.4 | Lint + format |

### Patterns to Follow

- **File naming**: kebab-case (`leaderboard-page.tsx`)
- **Components**: PascalCase exports, `"use client"` directive
- **Styling**: Tailwind utility classes, `cn()` from `@/lib/utils`
- **Animation**: `useScrollAnimation()` hook + `fadeInUp`/`staggerContainer` variants from `@/lib/animations`
- **Transitions**: `transitions.expo` (0.6s cinematic) for reveals
- **Data fetching**: TanStack Query with `useQuery()`
- **Pages**: `src/pages/` directory, lazy-loaded in `App.tsx`
- **Sections**: `src/components/sections/` for page sections
- **Magic UI**: Reuse `NumberTicker`, `BorderBeam`, `ShimmerButton` where appropriate
- **Theme**: Dark background (#161e2d), purple accent (#8351e5), Ember fonts

## Data Source

The Lambda writes `leaderboard.json` to S3 at:
```
s3://awsbaku-infrastructure-org-public-frontend/hackathon-leaderboard/leaderboard.json
```

Served via CloudFront at:
```
https://awsbaku.tech/hackathon-leaderboard/leaderboard.json
```

### leaderboard.json Shape

```typescript
interface LeaderboardData {
  updated_at: string;           // ISO 8601
  hackathon: {
    start: string;              // ISO 8601
    end: string;                // ISO 8601
  };
  rankings: TeamRanking[];
}

interface TeamRanking {
  rank: number;
  team: string;                 // Display name
  repo: string;                 // "awsbaku/team-slug"
  cumulative_score: number;     // Aggregated with diminishing returns
  pr_count: number;
  latest_eval: {
    overall_score: number;
    dimensions: {
      functional_value: number; // 0-10
      aws_integration: number;
      innovation: number;
      code_quality: number;
      documentation: number;
    };
  } | null;
  trend: "up" | "down" | "stable";
}
```

## Implementation Plan

### Files to Create

| File | Purpose |
|------|---------|
| `src/pages/leaderboard.tsx` | Main leaderboard page |
| `src/components/sections/leaderboard-header.tsx` | Hero section with title, countdown, last updated |
| `src/components/sections/leaderboard-table.tsx` | Rankings table with dimension breakdown |
| `src/hooks/use-leaderboard.ts` | TanStack Query hook for fetching + polling |
| `src/types/leaderboard.ts` | TypeScript interfaces |

### Files to Modify

| File | Change |
|------|--------|
| `src/App.tsx` | Add `/hackathon-leaderboard` route (lazy-loaded) |

### Step 1: TypeScript Types (`src/types/leaderboard.ts`)

Define `LeaderboardData`, `TeamRanking`, `DimensionScores` interfaces matching the JSON shape above.

### Step 2: Data Hook (`src/hooks/use-leaderboard.ts`)

```typescript
// TanStack Query hook with 30-second refetch interval
export function useLeaderboard() {
  return useQuery({
    queryKey: ["leaderboard"],
    queryFn: () => fetch("/hackathon-leaderboard/leaderboard.json").then(r => r.json()),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}
```

- Polls every 30 seconds (matches S3 CacheControl: max-age=30)
- Returns `{ data, isLoading, error, dataUpdatedAt }`
- `dataUpdatedAt` used for "last fetched X seconds ago" display

### Step 3: Leaderboard Header (`src/components/sections/leaderboard-header.tsx`)

- Event title: "AWS Bedrock Hackathon" with accent gradient
- Hackathon countdown timer (reuse existing `useCountdown` hook)
- "Last updated X seconds ago" using `dataUpdatedAt` from query
- Back link to landing page
- Uses `AuroraBackground` or `Meteors` for visual flair
- `useScrollAnimation` + `fadeInUp` for entrance

### Step 4: Leaderboard Table (`src/components/sections/leaderboard-table.tsx`)

**Desktop (md+)**: Full table layout
| Rank | Team | Score | PRs | Functional | AWS | Innovation | Quality | Docs | Trend |
|------|------|-------|-----|------------|-----|------------|---------|------|-------|

**Mobile (<md)**: Card layout (stacked)
```
#1  Team Alpha          7.2
    3 PRs | Latest: 7.8  ^
    [expand for dimensions]
```

**Visual details:**
- Rank #1: gold accent, #2: silver, #3: bronze (via Tailwind ring/border colors)
- Score displayed with `NumberTicker` component (animated counting)
- Trend arrow: Lucide `TrendingUp`/`TrendingDown`/`Minus` icons
- Dimension scores as mini progress bars (colored by score: red < 4, yellow 4-7, green > 7)
- Row expand/collapse for dimension details on click (Framer `AnimatePresence` + `motion.div`)
- Stagger animation on initial load (`staggerContainer` + `staggerItem`)

**Framer Motion for rank changes:**
- Use `layout` prop on `motion.div` rows for automatic reorder animation
- When rankings change on refetch, rows animate to new positions
- `layoutId={team.repo}` ensures correct element tracking

### Step 5: Leaderboard Page (`src/pages/leaderboard.tsx`)

Composes the sections:
```tsx
export function LeaderboardPage() {
  const { data, isLoading, error, dataUpdatedAt } = useLeaderboard();

  return (
    <main className="min-h-screen bg-background">
      <LeaderboardHeader
        hackathon={data?.hackathon}
        updatedAt={data?.updated_at}
        fetchedAt={dataUpdatedAt}
      />
      <LeaderboardTable
        rankings={data?.rankings ?? []}
        isLoading={isLoading}
      />
    </main>
  );
}
```

### Step 6: Route Registration (`src/App.tsx`)

```tsx
const LeaderboardPage = lazy(() =>
  import("./pages/leaderboard").then(m => ({ default: m.LeaderboardPage }))
);

<Routes>
  <Route path="/" element={<LandingPage />} />
  <Route path="/hackathon-leaderboard" element={
    <Suspense fallback={<LeaderboardSkeleton />}>
      <LeaderboardPage />
    </Suspense>
  } />
</Routes>
```

## Loading & Error States

**Loading (skeleton):**
- Header: shimmer placeholder for title + timer
- Table: 5 skeleton rows with pulsing animation (Tailwind `animate-pulse`)

**Error:**
- "Failed to load leaderboard" message with retry button
- Auto-retry after 10 seconds (TanStack Query `retry: 3`)

**Empty (no rankings yet):**
- "No scores yet -- evaluations will appear here during the hackathon"
- Countdown to hackathon start if before start time

## Accessibility

- `role="log"` on leaderboard container with `aria-live="polite"`
- `aria-atomic="false"` so only changed scores are announced
- Proper `<table>` semantics on desktop with `<th scope="col">`
- `aria-sort="descending"` on the Score column
- Focus-visible outlines on expandable rows
- Color-coded scores also have text labels (not color-only)

## Testing Plan

1. Create a mock `leaderboard.json` and place in `public/hackathon-leaderboard/`
2. `npm run dev` and navigate to `/hackathon-leaderboard`
3. Verify table renders, animations play, responsive layout works
4. Trigger actual eval on test-team-alpha to populate real data in S3
5. Verify live polling updates the table
6. `npm run build` + `npm run preview` to test production build
7. Deploy via tag and verify on awsbaku.tech/hackathon-leaderboard

## Status

- [x] Backend: Lambda + DynamoDB + Function URL deployed
- [x] Workflow: evaluate-prs.yml updated with leaderboard submission
- [x] Secrets/Variables: AWS_ROLE_ARN + LEADERBOARD_URL set
- [x] Codebase analysis: patterns, components, routing understood
- [ ] TypeScript types
- [ ] useLeaderboard hook
- [ ] LeaderboardHeader section
- [ ] LeaderboardTable section
- [ ] LeaderboardPage + route
- [ ] Loading/error/empty states
- [ ] Mock data testing
- [ ] End-to-end test with real eval
- [ ] Production deploy
