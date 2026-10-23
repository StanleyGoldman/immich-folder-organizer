# Immich Folder Organizer

A YAML-driven tool that declares Immich albums and the source paths whose assets should populate them. Replaces the folder-derived album-naming model of [salvoxia/immich-folder-album-creator](https://github.com/salvoxia/immich-folder-album-creator) with explicit declaration.

## Language

**Asset**:
An Immich photo or video. Immich treats photos and videos uniformly as assets — most operations apply to both. Use this term, not "image," "photo," or "file."
_Avoid_: Image, photo, file, picture, media

**Album**:
An Immich-side collection of assets, surfaced to the user in the Immich UI. Created and populated by this tool from YAML declarations. May coexist with manually-created albums in the same Immich instance.

**Source path**:
A directory referenced under an album's `paths:` list in the YAML config. Assets whose Immich-side location falls under a source path are added to that album. Several source paths may contribute to one album; an asset may be reached by source paths of multiple albums (and will be added to all of them).
_Avoid_: Root path, library path, folder

**Multi-album membership**:
An asset may belong to more than one album simultaneously — both via this tool (when matched by source paths under different albums) and via manual user action in Immich. Designing for this is a deliberate choice; the reference tool defaults to "orphan assets only" for performance.

**Marker-bearing album**:
An album whose description contains the tool's sentinel string. The marker means the tool created the album at some point in the past. It does not imply the tool is still managing it.
_Avoid_: Tagged album, owned album

**Tool-managed album**:
A marker-bearing album whose name matches a current YAML entry. The tool actively reconciles its asset list on every run.

**Orphaned album**:
A marker-bearing album whose name does NOT match any current YAML entry — i.e., the user removed the YAML entry but the album still exists in Immich. Left alone by default; deletable when the `delete_orphaned_albums` flag is set.

**Reconciliation**:
The act of making an Immich album match its YAML declaration on every run. Covers both:
- **Asset list** — assets matching the source paths are added; assets in the album that don't match are removed, regardless of whether they were added by the tool or by the user.
- **Properties** — description, sharing, thumbnail, sort order, and comments_and_likes are re-applied from YAML, overriding any manual edits.

The tool wins uniformly on declared fields: if the user has made changes in the Immich UI to a tool-managed album, the next run overwrites any field whose value is declared in YAML.

**Fields omitted from YAML are not reconciled.** If a YAML entry has no `share_with`, the tool does not touch sharing — manual shares set in the Immich UI persist. To explicitly reset a field, declare it with an empty/default value (`share_with: []`, etc.). `name` and `paths` are the only required fields on an album entry.

## Example dialogue

> **Dev**: Got a YAML entry — album "Italy 2023", source paths `[/external/photos/2023/Italy]`. What happens?
> **Domain**: Tool checks if "Italy 2023" album exists. If not, creates it. Then fetches assets under that source path and adds them.
> **Dev**: What about an asset already in the user's manually-created "Favorites" album?
> **Domain**: Doesn't matter — it still gets added to "Italy 2023". Multi-album membership is fine.
> **Dev**: And if I add the same path to another album in the YAML?
> **Domain**: Both albums get the assets. Source paths aren't exclusive.
