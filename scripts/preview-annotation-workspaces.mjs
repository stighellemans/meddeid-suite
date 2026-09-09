#!/usr/bin/env node
// Local development preview with synthetic data. Re-running preserves all edits.
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const suiteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const workspaceDir = path.join(suiteRoot, 'workspaces', 'annotation-preview');
const children = [];
let stopping = false;
const apps = [
  { repo: 'meddeid-annotate', kind: 'annotate', api: 8890, web: 5186, other: 5187 },
  { repo: 'meddeid-subannotate', kind: 'subannotate', api: 8891, web: 5187, other: 5186 },
  { repo: 'meddeid-curate', kind: 'curate', api: 8892, web: 5188 },
];
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  process.exitCode = code;
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
async function assertPortAvailable(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', () => reject(new Error(`Port ${port} is already in use. Stop the previous preview with Ctrl+C, then run this command again.`)));
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}
function start(args, cwd, env) {
  const child = spawn(process.execPath, args, { cwd, env: { ...process.env, ...env }, stdio: 'inherit' });
  children.push(child);
  child.on('exit', (code) => { if (!stopping) stop(code || 1); });
  return child;
}
async function ready(port) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (stopping) throw new Error('Preview stopped during startup.');
    try { if ((await fetch(`http://127.0.0.1:${port}/api/health`)).ok) return; } catch { /* still starting */ }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Server on port ${port} did not start.`);
}
const names = ['Alex Example', 'Robin Sample', 'Jamie Test', 'Morgan Demo'];
function notes(count, completed = 0) {
  return Array.from({ length: count }, (_, i) => {
    const name = names[i % names.length];
    const text = `${name} attended the demonstration clinic. This is a synthetic note for testing the MedDeID interface. The patient reports feeling well. A routine follow-up was discussed.`;
    return { document_id: `demo-note-${String(i + 1).padStart(3, '0')}`, text, annotated: i < completed, metadata: { lang: 'en-GB', collection: 'Synthetic interface demo' }, spans: [{ begin: 0, end: name.length, label: 'Name:Patient', text: name, category: 'Name', subtype: 'Patient' }] };
  });
}
async function seed(app) {
  if (app.kind === 'curate') {
    const dir = path.join(workspaceDir, 'example-imports');
    await fs.mkdir(dir, { recursive: true });
    for (const reviewer of ['a', 'b']) {
      const rows = notes(6, 6);
      if (reviewer === 'b') rows[0].spans[0] = { ...rows[0].spans[0], label: 'Name:Other', subtype: 'Other' };
      await fs.writeFile(path.join(dir, `curation-reviewer-${reviewer}.jsonl`), `${rows.map(row => JSON.stringify(row)).join('\n')}\n`, { flag: 'wx' }).catch(error => { if (error.code !== 'EEXIST') throw error; });
    }
    return;
  }
  const api = `http://127.0.0.1:${app.api}/api`;
  const existing = await (await fetch(`${api}/workspace`)).json();
  const trash = await (await fetch(`${api}/workspace/trash`)).json();
  const ledgerFile = path.join(workspaceDir, app.kind, '.preview-seeded.json');
  const seeded = new Set(await fs.readFile(ledgerFile, 'utf8').then(JSON.parse).catch(error => {
    if (error.code === 'ENOENT') return [];
    throw error;
  }));
  const sampleKey = entry => JSON.stringify([entry.dataset, entry.name]);
  for (const entry of [...existing.assignments, ...trash.items]) seeded.add(sampleKey(entry));
  await fs.writeFile(ledgerFile, JSON.stringify([...seeded], null, 2));
  const samples = app.kind === 'annotate' ? [
    { dataset: 'Demo · Outpatient notes', name: 'Training · Reviewer A', rows: notes(12, 4) },
    { dataset: 'Demo · Outpatient notes', name: 'Validation · Reviewer A', rows: notes(8, 0) },
    { dataset: 'Demo · Discharge notes', name: 'Test · Reviewer B', rows: notes(6, 6) },
    { dataset: 'Demo · Curation handoff', name: 'Training · Reviewer A', split:'training', rows: notes(2,2) },
    { dataset: 'Demo · Curation handoff', name: 'Training · Reviewer B', split:'training', rows: notes(2,2).map((r,i) => i ? r : {...r,spans:r.spans.map(s=>({...s,label:'Name:Other',subtype:'Other'}))}) },
  ] : [
    { dataset: 'Demo · Outpatient notes', name: 'Detailed review · Training', rows: notes(12, 12) },
    { dataset: 'Demo · Discharge notes', name: 'Detailed review · Test', rows: notes(6, 6) },
  ];
  for (const sample of samples) {
    if (seeded.has(sampleKey(sample))) continue;
    const filename = `${sample.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.jsonl`;
    const content = `${sample.rows.map((row) => JSON.stringify(row)).join('\n')}\n`;
    const examplesDir = path.join(workspaceDir, 'example-imports');
    await fs.mkdir(examplesDir, { recursive: true });
    await fs.writeFile(path.join(examplesDir, filename), content);
    const result = await fetch(`${api}/workspace/import`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...sample, rows: undefined, filename, content }) });
    if (!result.ok) throw new Error(`Could not prepare demo: ${await result.text()}`);
    seeded.add(sampleKey(sample));
    await fs.writeFile(ledgerFile, JSON.stringify([...seeded], null, 2));
  }
}
try {
  for (const app of apps) {
    await assertPortAvailable(app.api); await assertPortAvailable(app.web);
    const cwd = path.join(suiteRoot, 'repos', app.repo);
    await fs.access(path.join(cwd, 'node_modules', app.kind === 'curate' ? 'express' : 'fflate')).catch(() => { throw new Error(`Run npm ci in ${cwd} first.`); });
  }
  for (const app of apps) {
    const cwd = path.join(suiteRoot, 'repos', app.repo);
    const env = { MEDDEID_WORKSPACE_DIR: workspaceDir, HOST: '127.0.0.1', PORT: String(app.api), API_PORT: String(app.api), VITE_PORT: String(app.web), VITE_API_PROXY_TARGET: `http://127.0.0.1:${app.api}`, VITE_WORKSPACE_COMPANION_URL: app.other ? `http://127.0.0.1:${app.other}` : '', VITE_WORKSPACE_ANNOTATE_URL: 'http://127.0.0.1:5186', VITE_WORKSPACE_CURATE_URL: 'http://127.0.0.1:5188', VITE_WORKSPACE_SUBANNOTATE_URL: 'http://127.0.0.1:5187', MEDDEID_CURATE_DATA_DIR: path.join(workspaceDir, 'curate') };
    start(['server/index.js'], cwd, env);
    start(['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(app.web), '--strictPort'], cwd, env);
  }
  for (const app of apps) { await ready(app.api); await seed(app); }
  console.log(`\nReady — synthetic demo data, edits preserved between runs.\nAnnotate:    http://127.0.0.1:5186\nSubannotate: http://127.0.0.1:5187\nCurate:      http://127.0.0.1:5188\nSaved work:  ${workspaceDir}\nFrontend edits reload automatically. Stop with Ctrl+C.\n`);
} catch (error) { console.error(error.message); stop(1); }
