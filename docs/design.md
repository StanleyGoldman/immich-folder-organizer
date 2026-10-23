# Design

A YAML-driven tool that declares Immich albums and the source paths whose assets should populate them. Runs as a one-shot container, typically on a cron, against a single Immich user. Replaces folder-derived album naming (the reference's model) with explicit declaration and full-sync reconciliation.

For vocabulary: [GLOSSARY.md](../GLOSSARY.md). For the architectural rationale: [ADR-0001](./adr/0001-yaml-source-of-truth-full-sync.md).

## Configuration

### Connection (environment variables)

| Variable | Required | Description |
| --- | --- | --- |
| `IMMICH_URL` | yes | Root API URL, e.g. `http://immich-server:2283/api` |
| `IMMICH_API_KEY` | one of | Literal API key value |
| `IMMICH_API_KEY_FILE` | one of | Path to a file containing the API key (for Docker secret mounts) |
| `APPLY` | no | `1` to commit changes. Defaults to dry-run — tool prints what it *would* do without changing anything. |
| `CRON_EXPRESSION` | no | If set, container schedules itself via in-container cron. If unset, runs once and exits. |
| `RUN_ON_STARTUP` | no | When set alongside `CRON_EXPRESSION`, runs the tool once immediately on container start before handing off to cron. Useful for verifying config without waiting for the first tick. Ignored when `CRON_EXPRESSION` is unset (one-shot mode already runs on start). |
| `TZ` | no | Timezone for the cron schedule. |
| `CONFIG_FILE` | no | Path to the album YAML inside the container. Default `/config/albums.yaml`. |

Exactly one of `IMMICH_API_KEY` / `IMMICH_API_KEY_FILE` must be set.

### Album YAML

A single file, mounted into the container. Every album is a top-level entry under `albums:`. Only `name` and `paths` are required; everything else is optional.

```yaml
albums:
  # Minimal: name + paths.
  - name: "Italy 2023"
    paths:
      - /external/photos/2023/Italy

  # Multiple source paths feed one album.
  - name: "Vacations 2023"
    paths:
      - /external/photos/2023/Italy
      - /external/photos/2023/Japan
      - /external/photos/2023/Spain

  # Subtree-recursive paths with literal-subpath exclusions.
  - name: "Family 2024"
    paths:
      - /external/photos/2024
    exclude:
      - /external/photos/2024/private
      - /external/photos/2024/_thumbnails

  # All album properties shown. All optional. Omitted fields are not reconciled.
  - name: "Iceland 2024"
    description: "Ring Road, September 2024"
    sort_order: desc            # asc | desc
    thumbnail: random           # first | last | random | <absolute asset path>
    comments_and_likes: true
    share_with:
      - user: spouse            # username OR email both work
        role: editor            # viewer | editor
      - user: friend@example.com
        role: viewer
    paths:
      - /external/photos/2024/Iceland
```

#### Top-level options

```yaml
delete_orphaned_albums: false   # default: never delete tool-managed albums when their YAML entry is removed.
                                # set true to opt in.
```

### Field semantics

- **`paths`** — each entry is a directory path *as Immich sees it* (the post-mount path the Immich API returns). Subtree-recursive: `/photos/2023` matches every asset under `/photos/2023/**`.
- **`exclude`** — same subtree-recursive semantics. An asset matching both an include and an exclude is excluded.
- **`share_with[].user`** — matched against username and email both. Non-existent users cause the share to be skipped with a warning, not a hard failure.
- **`share_with[].role`** — `viewer` or `editor`. Defaults to `viewer` if omitted.
- **`thumbnail: random`** — re-rolls every run. There is no "pick random once and stick" mode in v1.
- **Omitted fields are not reconciled.** Omitting `share_with` lets manual shares persist. To wipe a field, declare it explicitly (`share_with: []`, `description: ""`).

## Behavior

On every run:

1. **Load YAML.** Parse `CONFIG_FILE`.
2. **Authenticate.** Connect to Immich using `IMMICH_URL` + the API key. Requires Immich v3.
3. **For each album in YAML:**
   - Look up by name among the albums the API key's user owns (albums shared with that user are ignored). If absent, create it with the marker in the description.
   - If present and marker-bearing → already managed.
   - If present and marker-less → **adopt with warning** (log loudly, add marker, proceed).
   - Reconcile asset list: query Immich for assets whose path is under any include path and not under any exclude path. Add missing, remove extras. Only timeline assets are matched; archived, hidden and locked assets never are, so an archived asset already in the album counts as an extra.
   - Reconcile declared properties (description, share_with, etc.). Omitted fields untouched. The album owner is never treated as a share, so `share_with` cannot revoke it.
4. **If `delete_orphaned_albums: true`:** find marker-bearing albums whose names are not in YAML, delete them.
5. **If `APPLY` unset:** print everything as a preview, change nothing.

## Deployment

### docker-compose snippet

```yaml
services:
  immich-folder-organizer:
    image: immich-folder-organizer:latest
    restart: unless-stopped
    user: 1000:1000
    environment:
      IMMICH_URL: http://immich-server:2283/api
      IMMICH_API_KEY_FILE: /run/secrets/immich_api_key
      CRON_EXPRESSION: "0 * * * *"
      TZ: America/New_York
      APPLY: "1"
    secrets:
      - immich_api_key
    volumes:
      - ./albums.yaml:/config/albums.yaml:ro

secrets:
  immich_api_key:
    file: ./immich_api_key.secret
```

### Running ad-hoc

Single one-shot dry-run (no cron, no apply):

```bash
docker run --rm \
  -e IMMICH_URL=http://immich-server:2283/api \
  -e IMMICH_API_KEY=$KEY \
  -v ./albums.yaml:/config/albums.yaml:ro \
  immich-folder-organizer:latest
```

Add `-e APPLY=1` to commit. Omit `CRON_EXPRESSION` — when unset, the container runs once and exits.

## Out of scope for v1

Explicit non-goals, recorded so they don't get re-litigated:

- **Folder-derived albums** (the reference's `--album-levels` / `--album-separator` / `--album-name-post-regex`). YAML is the only album surface.
- **Per-folder `.albumprops` files.** Properties live in YAML.
- **Multi-user in one process.** One API key per container; run multiple containers for multi-user.
- **Glob path patterns.** Paths and excludes are literal subtree prefixes.
- **Asset visibility manipulation** (archive / locked). Cut from album properties as too destructive.
- **Sidecar state file.** Album-level ownership via the marker is sufficient; asset-level ownership (preserving manual asset additions) is deferred until needed.
- **Long-running daemon / filesystem watcher.** One-shot container only.
