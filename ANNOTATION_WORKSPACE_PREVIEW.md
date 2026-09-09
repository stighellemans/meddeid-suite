# Shared annotation workspace preview

Annotate, Curate and Subannotate keep persistent, switchable assignments or comparisons. The functionality is included in the published 0.3.1 images; this preview uses the local checkouts for fast development iteration.

## Fast local iteration

From `meddeid-suite`:

```bash
node scripts/preview-annotation-workspaces.mjs
```

Open Annotate at <http://127.0.0.1:5186>, Subannotate at <http://127.0.0.1:5187>, and Curate at <http://127.0.0.1:5188>. The script starts three APIs and Vite clients. Synthetic assignments are seeded once; existing work is preserved, and removed samples are not recreated on restart. The “Demo · Curation handoff” reviewers provide a two-document example with one disagreement.

Frontend edits reload automatically. Restart the command after server changes. Ctrl+C stops the preview. Run `npm ci` in each app checkout first if dependencies are missing. Ports 5186–5188 and 8890–8892 must be available.

## User flow

1. **Annotate:** Import annotation-ready JSONL and complete a separate assignment for each reviewer. Dataset and assignment names identify the work.
2. **Curate:** Choose **New comparison → From workspace**. Select at least two completed reviewer assignments for the same documents, give the comparison a name, and open it. File import remains available for work coming from elsewhere.
3. Resolve differences, confirm the documents, and **Publish gold**. Switch comparisons through **Workspace** or return to **All comparisons**. Each comparison keeps its decisions and frozen input copies. Starting another comparison does not replace existing work.
4. **Subannotate:** Use **Workspace → Continue in Subannotate** from Curate, or **From workspace** in the Subannotate library. Select a finalized curation version or a completed Annotate assignment and create a detailed review. A matching existing review can be resumed instead. If curation is unnecessary, completed Annotate work can go directly to Subannotate.
5. Export a bundle only when you need a portable copy or want to share the result. **No bundle download, file copying or renaming is required between these apps in the shared workspace.**

When a selected reviewer source has changed, creation fails with a refresh instruction instead of silently taking a different version. Nonempty split labels must agree; Curate also validates document/text compatibility. Each finalized curation version remains available even after subsequent edits or publication. Subannotate keeps its selected snapshot until you explicitly apply a previewed source update; compatible detailed labels carry forward.

## Inherited suggestion profiles

New Subannotate assignments inherit the project's language through the frozen
records' `metadata.lang`. English (`en-GB`, `en-US`) and Dutch (`nl-BE`, `nl-NL`)
capabilities are included in the application's pinned npm dependencies, so both
`npm ci` for this preview and the Docker image supply them automatically.
Run `npm ci` in `repos/meddeid-subannotate` after updating an older checkout.
Mixed supported locales route per document. **Files & results → Suggestion
profile** shows the inherited profile. The assignment and exported work preserve
its descriptor and package versions; future process configuration cannot silently
switch an inherited managed review's profile. A changed installed implementation
is rejected when reopening rather than silently changing suggestions.

Existing reviews retain their previous profile. Missing, ambiguous or unsupported
language metadata requires an explicit **Use language-neutral suggestions** choice
in either the workspace handoff or file import dialog. There is no guessed locale
or automatic fallback for a known unsupported language.

## Full-height review

Every app has the same **Annotate / Curate / Subannotate** navigation. The current app is highlighted. Links open the destination library in the same browser tab, including on narrow screens. Expand **Workspace** to access navigation while reviewing. Switching applications uses the same pending-save and unsaved-change checks as switching assignments.

The small **Workspace** button in each original editor toolbar expands the workspace controls. Clicking outside that region collapses them again. The preference is remembered per app, and collapsing does not remount the editor or discard a draft. The collapsed editor gets the full viewport height.

Switching waits for pending saves. Annotate offers **Save & switch** for drafts; Subannotate preserves its confirmation state. Curate automatically saves decisions and offers retry/discard controls for a failed change. The last document is remembered per assignment in the browser.

## Frequent source corrections

Curate and Subannotate show **Newer source available** in the original editor toolbar. Checks run on opening, tab focus and every 30 seconds while visible. For saved work, click the notice to prepare a preview, then **Update this review**. Unsaved edits can be saved before previewing. Existing review IDs and names stay the same, and the editor opens affected work after updating.

Curate carries compatible decisions/additions/overrides and resets changed document confirmations. Subannotate retains compatible detailed labels and flags changed text/labels or unsafe matches. Curation must be republished before downstream detailed review can consume changes. Language-profile pins remain unchanged; incompatible language changes are blocked. If either source or saved work changes after preview, another preview is required. Older tabs cannot save over an updated review.

**Source updates → Recovery versions** restores a previous state while retaining current work as another recovery version. Recovery uses content-addressed files inside the assignment's `.source-history/` folder, avoiding nested copies over repeated updates. A journal rolls back an interrupted installation before the review reopens. Export folders and immutable published versions are retained; older work-directory archives are included in their recovery snapshot. Backup the full workspace, including dotfolders. File-only imports have no linked workspace ancestor to monitor.

## Removing and restoring work

In each app, open an assignment or comparison, expand **Workspace**, then choose **Files & results**. **Remove from workspace…** is a quiet action at the bottom of that dialog. The warning identifies the item and known downstream work; type its exact name before choosing **Move to trash**. Finish saving local edits first. Removal waits for queued saves and moves the complete item folder, including inputs, saved work, exports and finalized versions.

Open **Local workspace → Trash** to restore an item. From Files & results, **Workspace storage → Trash** leads to the same place. Restoration preserves the original ID, progress and files. Trash is retained indefinitely, including across app restarts. Permanent deletion is a separate action inside Trash requiring both the exact name and an explicit acknowledgement that it cannot be undone.

Removal affects only the selected assignment or comparison in the current app. Other apps retain their frozen input copies and saved work. Trashed sources disappear from new-input pickers. Copies downloaded outside this workspace are unaffected. Trash lives at `<app>/.trash/<id>/` within the shared workspace; keep it when backing up the workspace.

## Data and results

Saved work lives in `workspaces/annotation-preview`:

- `annotate/<id>/` and `subannotate/<id>/`: `assignment.json`, preserved `source.jsonl`, editable `work/`, and timestamped bundle copies in `exports/`.
- `curate/<id>/`: `assignment.json`, frozen `inputs/`, editable `work/project.json`, immutable finalized versions under `results/<version>/`, and bundle copies in `exports/`.

Each finalized Curate version includes annotations, decision audit, export manifest, and result provenance. **Files & results** shows source versions and storage paths. Exported bundles include checksums and are labelled completed or in progress. Annotation file imports are limited to 20 MB; Curate accepts JSONL files and matching manifests within its 50 MB request limit. ZIP import and CSV/Parquet conversion are not included.

If a previous single Curate comparison exists at `curate/project.json`, the workspace copies it once into “Previous comparison,” preserves its old published gold, and leaves the original files untouched. Republish after verifying that comparison to mark its current state finalized. Standalone Curate without `MEDDEID_WORKSPACE_DIR` retains its legacy workflow.

Keep the entire workspace folder to retain inputs, provenance, decisions, versions and detailed reviews. Run only one instance of each app against it. Separate reviewers should use separate assignments; simultaneous editing of the same assignment by multiple people is not a collaboration/locking feature.

## Docker

Stop the local preview, then run:

```bash
docker compose -f compose.annotation-workspaces.yaml up --build
```

This is **one command starting three persistent containers**, one per application. There is no new container per dataset, split, reviewer or comparison. All three share the same mounted workspace and browser ports. Rebuild for code changes; importing or switching work needs no rebuild or restart. Paths shown inside Docker map to the host workspace directory. If changing the exposed ports or hostname, also update the frontend companion URLs in the Compose build arguments.

## Validation

Run `npm test` and `npm run build` in all three app repositories. Tests cover assignment and comparison isolation, restart persistence, versioned curation, legacy migration, frozen handoffs, invalid/stale source rejection, export checksums, typed deletion confirmation, full-file trash/restore preservation, downstream preservation, and prevention of legacy comparison resurrection. The browser preview supports fast end-to-end iteration on the synthetic handoff example.
