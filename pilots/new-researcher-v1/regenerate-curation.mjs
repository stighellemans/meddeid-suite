import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { createProjectStore } from '../../repos/meddeid-curate/server/project-store.js';

const pilotRoot = path.dirname(fileURLToPath(import.meta.url));
const suiteRoot = path.resolve(pilotRoot, '..', '..');
const curateRoot = path.join(suiteRoot, 'repos', 'meddeid-curate');
const primaryRoot = path.join(pilotRoot, '02-primary');
const outputRoot = path.join(pilotRoot, '03-adjudication');
const curatorId = 'pilot-curator-v2';

const inputs = await Promise.all(
  ['annotator-a.jsonl', 'annotator-b.jsonl'].map(async (name) => ({
    name,
    content: await fs.readFile(path.join(primaryRoot, name), 'utf8'),
  })),
);

const workRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'meddeid-pilot-curation-'));
try {
  const store = createProjectStore({ rootDir: curateRoot, dataDir: workRoot });
  await store.load();
  let state = await store.importFiles(inputs, { curatorId });
  const annotatorAId = state.project.sources.find(
    (source) => source.filename === 'annotator-a.jsonl',
  )?.annotation_set_id;
  if (!annotatorAId) throw new Error('Could not resolve annotator A identity');

  // The original pilot deliberately injected disagreements into annotator B.
  // The adjudicated fixture retains annotator A for each disputed group while
  // recording a durable, explicit decision for every alternative.
  for (const document of state.project.documents) {
    for (const disagreement of document.disagreements) {
      const candidate = disagreement.candidates.find((item) =>
        item.present_in.includes(annotatorAId));
      if (!candidate) {
        throw new Error(
          `${document.document_id}/${disagreement.disagreement_id} has no annotator A candidate`,
        );
      }
      state = await store.resolveDisagreement(
        document.document_id,
        disagreement.disagreement_id,
        {
          decision: 'accept_candidate',
          candidateId: candidate.candidate_id,
          curatorId,
        },
      );
    }
    state = await store.confirmDocument(document.document_id, { curatorId });
  }

  if (state.stats.pending !== 0 || state.stats.confirmedDocuments !== 6) {
    throw new Error(`Unexpected completed curation stats: ${JSON.stringify(state.stats)}`);
  }
  const published = await store.finalize();
  if (published.manifest.counts.primary_gold_spans !== 22) {
    throw new Error(
      `Expected 22 primary gold spans, found ${published.manifest.counts.primary_gold_spans}`,
    );
  }
  await fs.mkdir(outputRoot, { recursive: true });
  await Promise.all([
    fs.copyFile(published.annotationsPath, path.join(outputRoot, 'annotations.jsonl')),
    fs.copyFile(published.decisionsPath, path.join(outputRoot, 'decisions.jsonl')),
    fs.copyFile(published.manifestPath, path.join(outputRoot, 'manifest.json')),
  ]);
  console.log(
    `Published ${published.manifest.counts.documents} resolved pilot documents ` +
    `with ${published.manifest.counts.primary_gold_spans} spans.`,
  );
} finally {
  await fs.rm(workRoot, { recursive: true, force: true });
}
