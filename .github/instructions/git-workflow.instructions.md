# Git Workflow — Branching & Commit Standards

**Applies to:** All work in this repository.

---

## Branch Structure

```
main          ← Production-ready. Only receives merges from dev. Never commit directly.
  └── dev     ← Integration branch. All feature work merges here first.
       ├── feature/add-org-shape
       ├── fix/iri-encoding-bug
       ├── docs/update-api-reference
       └── chore/upgrade-orjson
```

### Protected branches

| Branch | Direct commits | Force push | Receives merges from |
|--------|---------------|------------|----------------------|
| `main` | ❌ Never | ❌ Never | `dev` only |
| `dev`  | ❌ Never | ❌ Never | Topic branches only |

---

## Branch Naming Convention

All topic branches must use a **type prefix** followed by a `/` and a kebab-case description.

| Prefix | Use when... | Example |
|--------|-------------|---------|
| `feature/` | Adding new functionality | `feature/organization-shape` |
| `fix/` | Fixing a bug | `fix/csv-encoding-error` |
| `docs/` | Documentation-only changes | `docs/add-cosmos-guide` |
| `refactor/` | Restructuring without behaviour change | `refactor/pipeline-internals` |
| `test/` | Adding/fixing tests only | `test/add-excel-adapter-tests` |
| `chore/` | Dependency updates, CI config, tooling | `chore/bump-structlog` |
| `perf/` | Performance improvements | `perf/optimize-builder-loop` |
| `hotfix/` | Urgent fix for production (branches from `main`) | `hotfix/cosmos-auth-crash` |

**Rules:**
- Use lowercase only
- Use hyphens, not underscores or spaces
- Keep names short but descriptive (3–5 words max)
- Include issue number when applicable: `fix/42-null-birthdate`

---

## Commit Message Convention (Conventional Commits)

All commits follow the [Conventional Commits 1.0.0](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed types

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, whitespace (no logic change) |
| `refactor` | Code restructuring (no feature/fix) |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system or dependencies (`pyproject.toml`, etc.) |
| `ci` | CI/CD configuration |
| `chore` | Maintenance tasks |
| `revert` | Reverting a previous commit |

### Scopes (optional but encouraged)

Use the module or area being changed: `pipeline`, `builder`, `mapper`, `cosmos`, `cli`, `adapters`, `shacl`, `registry`, `serializer`, `validator`, `logging`, `sanitize`.

### Examples

```
feat(pipeline): add dead-letter queue for failed records
fix(builder): sanitize IRI components to prevent injection
docs: update README with production features
test(adapters): add Excel adapter edge case tests
refactor(pipeline): extract progress tracking into helper
build: add structlog and tqdm to optional deps
chore: update .gitignore for Sphinx build artifacts
perf(serializer): switch to orjson bulk serialization

feat(pipeline)!: return PipelineResult instead of int from to_json

BREAKING CHANGE: to_json() and to_ndjson() now return PipelineResult.
Use result.bytes_written for the previous int value.
```

### Rules

- **Subject line:** imperative mood, lowercase, no period, max 72 chars
- **Body:** wrap at 72 chars, explain *what* and *why* (not *how*)
- **Breaking changes:** append `!` after type/scope AND add `BREAKING CHANGE:` footer
- **One logical change per commit.** Don't mix a feature + a refactor + a test fix in one commit.

---

## Workflow — Day-to-Day Development

### Starting new work

```powershell
# 1. Make sure dev is up to date
git checkout dev
git pull origin dev

# 2. Create a topic branch
git checkout -b feature/my-new-feature

# 3. Do your work, commit often with conventional commits
git add -A
git commit -m "feat(pipeline): add progress callback support"

# 4. Push your branch
git push -u origin feature/my-new-feature
```

### Completing a feature (merge to dev)

```powershell
# 1. Make sure dev hasn't diverged
git checkout dev
git pull origin dev
git checkout feature/my-new-feature
git rebase dev    # or merge — see merge strategy below

# 2. Run tests to confirm everything passes
python -m pytest tests/ -v --tb=short

# 3. Merge into dev (use --no-ff to preserve branch history)
git checkout dev
git merge --no-ff feature/my-new-feature -m "feat(pipeline): add progress callback support"

# 4. Push dev
git push origin dev

# 5. Delete the topic branch (local and remote)
git branch -d feature/my-new-feature
git push origin --delete feature/my-new-feature
```

### Releasing to main

Only merge `dev` → `main` when `dev` is stable and all tests pass.

```powershell
# 1. Ensure dev is clean and tested
git checkout dev
git pull origin dev
python -m pytest tests/ -v --tb=short

# 2. Merge dev into main
git checkout main
git pull origin main
git merge --no-ff dev -m "release: merge dev into main"

# 3. Tag the release (SemVer)
git tag -a v1.0.0 -m "v1.0.0 — Phase 7 complete"

# 4. Push main and tags
git push origin main --tags
```

### Hotfixes (urgent production fixes)

```powershell
# Branch from main, not dev
git checkout main
git checkout -b hotfix/critical-cosmos-bug

# Fix, test, commit
git commit -m "fix(cosmos): handle null partition key"

# Merge into BOTH main and dev
git checkout main
git merge --no-ff hotfix/critical-cosmos-bug
git checkout dev
git merge --no-ff hotfix/critical-cosmos-bug

# Push both, delete hotfix branch
git push origin main dev
git branch -d hotfix/critical-cosmos-bug
git push origin --delete hotfix/critical-cosmos-bug
```

---

## Merge Strategy

- **Topic → dev:** Use `--no-ff` (no fast-forward) to preserve branch history in the graph.
- **dev → main:** Always `--no-ff` merge. Never rebase main.
- **Keeping topic branch current:** Prefer `git rebase dev` for a clean linear history on the topic branch. Use `git merge dev` if the branch is shared with others.

---

## Agent-Specific Rules

When I (the AI agent) am working on code changes:

1. **Always check the current branch** before making changes: `git branch --show-current`
2. **Never commit directly to `main` or `dev`.** Create a topic branch first.
3. **Create the topic branch from `dev`** unless it's a hotfix (then branch from `main`).
4. **Commit with Conventional Commits** format — every single time.
5. **Run tests before merging** — verify the suite passes on the topic branch.
6. **After completing a feature**, merge the topic branch into `dev`, push, and clean up.
7. **Do not push to `main`** unless the user explicitly says "release" or "merge to main".
8. **Use atomic commits** — one logical change per commit. Don't lump unrelated changes.
9. **Always push the branch** after committing so work is backed up to the remote.
10. **Include the scope** in commit messages when the change touches a specific module.

### Workflow for a typical agent task

```
git checkout dev && git pull origin dev       # sync
git checkout -b feature/my-task               # branch
# ... make changes, run tests ...
git add -A && git commit -m "feat(scope): description"
git push -u origin feature/my-task            # backup
git checkout dev && git merge --no-ff feature/my-task
git push origin dev                           # integrate
git branch -d feature/my-task                 # clean up local
git push origin --delete feature/my-task      # clean up remote
```

---

## Tags & Versioning

- Follow [SemVer 2.0](https://semver.org/): `MAJOR.MINOR.PATCH`
- Tag format: `v1.2.3`
- Tag on `main` only, after merging from `dev`
- `feat` commits → bump MINOR
- `fix` commits → bump PATCH
- `BREAKING CHANGE` → bump MAJOR
