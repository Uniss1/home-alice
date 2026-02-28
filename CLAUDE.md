# home-alice

Система голосового управления Windows PC через Yandex Alice с 16 интегрированными инструментами


## Working with Tasks

All tasks are managed through GitHub Issues.

### View open tasks:
```bash
gh issue list --repo Uniss1/home-alice --state open
```

### Before starting work:
```bash
gh issue view <NUMBER> --repo Uniss1/home-alice
gh issue view <NUMBER> --repo Uniss1/home-alice --comments
```

### Workflow:
1. Read the issue fully (description + comments) — it's your memory
2. Comment start: `gh issue comment <N> --repo Uniss1/home-alice --body "Starting work"`
3. Do the work
4. Comment result: `gh issue comment <N> --repo Uniss1/home-alice --body "Done: <summary>"`
5. Close if done: `gh issue close <N> --repo Uniss1/home-alice`

### Creating tasks:
```bash
gh issue create --repo Uniss1/home-alice --title "Title" --body "Description" --label "feature"
```

### Labels:
- `feature` — new feature or enhancement
- `bug` — something isn't working
- `refactor` — code refactoring
- `research` — research or investigation
- `priority:high` / `priority:medium` / `priority:low`

### Rules:
1. Always read the issue BEFORE starting work
2. Always comment on the issue with progress
3. One issue = one task. Don't mix work across issues
4. Never delete issues — close them with a summary comment
