# 0001 — YAML as source of truth, full-sync reconciliation

## Context

The reference tool ([salvoxia/immich-folder-album-creator](https://github.com/salvoxia/immich-folder-album-creator)) derives album names from folder structure (via `--album-levels`, `--album-separator`, `.albumprops` overrides) and is add-only — it never removes assets from albums or deletes albums. Identity is name-only; the tool can't tell its own albums apart from manually-created ones.

We deliberately invert this on every axis.

## Decision

1. **Albums are declared, not derived.** A YAML config lists albums by name and their source paths. There is no folder-derivation engine, no `.albumprops`-style override layer.
2. **Asset membership is full-sync.** Each run, every tool-managed album's asset list becomes exactly the assets currently reachable from its source paths. Missing assets are added; extra assets are removed.
3. **The tool wins on manual edits.** If the user manually adds or removes an asset from a tool-managed album in the Immich UI, the next run reconciles it away. Manual curation must live in albums not declared in the YAML.
4. **Albums are identified by a sentinel marker** written into the album description. Marker-bearing albums are distinguishable from manually-created ones with the same name.
5. **Albums are never deleted by default.** Removing an album from YAML leaves the album shell (now [[orphaned]]) and its current contents in place — the tool simply stops touching it. An opt-in `delete_orphaned_albums: true` config flag enables deletion of marker-bearing orphaned albums.

## Considered alternatives

- **Folder-derived naming (reference's model).** Rejected: ~7 of the reference's 30 options exist to bandage the derivation engine (negative levels, ranges, regex post-processing, `.albumprops` overrides). Declarative YAML cuts that complexity entirely.
- **Add-only asset membership (reference's default).** Rejected: defeats the point of a declarative config — you could declare albums but not un-declare their contents.
- **Owned-sync via sidecar state file.** Rejected for now: state file adds backup, sync-corruption, and migration concerns for asset-level ownership we don't yet need. Marker-based album-level ownership covers the common case; we can graduate to a state file if/when preserving manual asset edits becomes important.
- **Name-only identity (no marker).** Rejected: leaves no escape hatch for cleaning up orphaned albums, and silently risks "managing" albums the user made by hand that happen to share a name.

## Consequences

- Users must adopt "tool wins" discipline: manual curation lives in albums outside the YAML.
- Multi-album membership is allowed, which forces the tool to fetch all assets under the source paths (not just orphans). On large libraries this is slower than the reference's default. Accepted trade-off.
- Collision behavior — when a YAML entry names an album that exists but lacks the marker — is "adopt with warning": the tool adds its marker, logs the adoption event prominently, and starts reconciling the album. Chosen to give a smooth migration path from the reference tool (which leaves un-marked albums all over Immich); the loud per-album log preserves user agency to spot accidental adoption of a hand-curated album and remove the marker manually.
