import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

import { createProjectStore } from '../../repos/meddeid-subannotate/server/project-store.js';

const execFileAsync = promisify(execFile);
const pilotRoot = path.dirname(fileURLToPath(import.meta.url));
const suiteRoot = path.resolve(pilotRoot, '..', '..');
const appRoot = path.join(suiteRoot, 'repos', 'meddeid-subannotate');
const sourcePath = path.join(pilotRoot, '03-adjudication', 'annotations.jsonl');
const outputRoot = path.join(pilotRoot, '04-subannotation');
const priorRows = (await fs.readFile(path.join(outputRoot, 'subannotations.jsonl'), 'utf8'))
  .split(/\r?\n/)
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line));

const confirmedImports = priorRows.map((row) => ({
  document_id: row.document_id,
  subannotations: row.items.flatMap((item) => item.segments),
}));
const importedSegmentCount = confirmedImports.reduce(
  (sum, row) => sum + row.subannotations.length,
  0,
);
if (confirmedImports.length !== 6 || importedSegmentCount !== 92) {
  throw new Error(
    `Expected 6 documents and 92 reviewed segments, found ` +
    `${confirmedImports.length} and ${importedSegmentCount}`,
  );
}

const workRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'meddeid-pilot-subannotation-'));
let installed = false;
try {
  await execFileAsync(process.execPath, ['server/prepare-data.js'], {
    cwd: appRoot,
    env: {
      ...process.env,
      MEDDEID_DATA_DIR: workRoot,
      MEDDEID_ANNOTATIONS_PATH: sourcePath,
    },
  });
  const importDir = path.join(workRoot, 'subspan_annotations', 'imports');
  await fs.mkdir(importDir, { recursive: true });
  await fs.writeFile(
    path.join(importDir, 'confirmed_subannotations.jsonl'),
    `${confirmedImports.map((row) => JSON.stringify(row)).join('\n')}\n`,
    'utf8',
  );

  const store = await createProjectStore({ rootDir: appRoot, dataDir: workRoot });
  const bootstrap = await store.getBootstrap();
  if (bootstrap.progress.spans.confirmed !== 22) {
    throw new Error(
      `Expected all 22 spans to be restored as confirmed, found ` +
      `${bootstrap.progress.spans.confirmed}`,
    );
  }
  const bundle = await store.exportEvaluationBundle();
  if (
    bundle.manifest.counts.documents !== 6 ||
    bundle.manifest.counts.primary_gold_spans !== 22 ||
    bundle.manifest.counts.core_pii_subannotations !== 92
  ) {
    throw new Error(`Unexpected evaluation bundle counts: ${JSON.stringify(bundle.manifest.counts)}`);
  }

  const backupRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'meddeid-pilot-subannotation-backup-'));
  await fs.rename(outputRoot, path.join(backupRoot, '04-subannotation'));
  await fs.cp(workRoot, outputRoot, { recursive: true });
  // The source link is machine-local by design and is recreated on the first
  // `npm run dev` from MEDDEID_ANNOTATIONS_PATH. Do not check an absolute
  // workstation path into the portable pilot fixture.
  await fs.rm(path.join(outputRoot, 'annotation-source.json'), { force: true });
  installed = true;
  console.log(
    `Regenerated the current subannotation workspace and evaluation bundle; ` +
    `previous fixture retained at ${backupRoot}.`,
  );
} finally {
  if (installed) await fs.rm(workRoot, { recursive: true, force: true });
}
