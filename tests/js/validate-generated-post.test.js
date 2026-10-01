import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import { validatePost } from '../../scripts/validate-generated-post.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', '..', 'scripts', 'validate-generated-post.js');
const REPO_ROOT = path.join(HERE, '..', '..');

const CHANGES = [
  '- the exporter now writes a coverage block',
  '- the refresh script stages new geometry instead of asking for it',
  '- a regeneration that got worse cannot be published',
].join('\n');

const FILLER = 'This release note carries enough prose to clear the word floor. '.repeat(12);

function post({ frontmatter = {}, body = `${FILLER}\n\n${CHANGES}\n` } = {}) {
  const fields = {
    title: '"v1.2.0"',
    date: '2026-01-15',
    description: '"v1.2.0 adds a coverage block and two fixes."',
    ...frontmatter,
  };
  const lines = Object.entries(fields).map(([key, value]) => `${key}: ${value}`);
  return `---\n${lines.join('\n')}\n---\n\n${body}`;
}

function rules(content, cfg) {
  return validatePost(content, cfg).failures.join('\n');
}

// -- happy path -------------------------------------------------------------

test('a well-formed generated post passes every check', () => {
  const { failures } = validatePost(post());
  assert.deepEqual(failures, []);
});

// -- 1. placeholder text ----------------------------------------------------

test('placeholder text left by an empty change list fails', () => {
  const body = `${FILLER}\n\n| Change | Notes |\n|---|---|\n| General improvements | See release notes |\n`;
  assert.match(rules(post({ body })), /placeholder text/);
});

test('the placeholder list is configurable', () => {
  const body = `${FILLER}\n\n- coming soon\n`;
  assert.match(rules(post({ body }), { placeholderPhrases: ['coming soon'] }), /placeholder text/);
});

// -- 2. empty description ---------------------------------------------------

test('a description that trails off fails', () => {
  const frontmatter = { description: '"v1.2.0 adds ."' };
  assert.match(rules(post({ frontmatter })), /description is effectively empty/);
});

test('a blank description fails', () => {
  assert.match(rules(post({ frontmatter: { description: '""' } })), /description is effectively empty/);
});

test('a post with no description field at all is not flagged for it', () => {
  const content = `---\ntitle: "v1.2.0"\n---\n\n${FILLER}\n\n${CHANGES}\n`;
  assert.doesNotMatch(rules(content), /description/);
});

// -- 3. raw commit SHAs -----------------------------------------------------

test('a summary of raw commit SHAs fails', () => {
  const frontmatter = { summary: '"a1b2c3d fix the thing, 9f8e7d6 fix the other thing"' };
  assert.match(rules(post({ frontmatter })), /summary contains a raw commit SHA/);
});

test('an ordinary summary passes', () => {
  const frontmatter = { summary: '"Two fixes and a new coverage block."' };
  assert.doesNotMatch(rules(post({ frontmatter })), /raw commit SHA/);
});

// -- 4. word count ----------------------------------------------------------

test('a body under the floor fails', () => {
  assert.match(rules(post({ body: 'Too short.\n\n- one change\n' })), /minimum 100/);
});

test('the floor is configurable', () => {
  const { failures } = validatePost(post({ body: 'Short.\n\n- one change\n' }), {
    minWordCount: 2,
    placeholderPhrases: [],
    requireChangeList: true,
  });
  assert.deepEqual(failures, []);
});

// -- 5. change list ---------------------------------------------------------

test('a post with no change list fails', () => {
  assert.match(rules(post({ body: FILLER })), /no change list found/);
});

test('a legacy change table counts as a change list', () => {
  const body = `${FILLER}\n\n| Change | Notes |\n|---|---|\n| coverage block | added |\n| refresh script | fixed |\n`;
  assert.doesNotMatch(rules(post({ body })), /no change list/);
});

test('bullets under any heading count, not just Features and Fixes', () => {
  const body = `${FILLER}\n\n### Coverage — more of the export is checked\n\n${CHANGES}\n`;
  assert.doesNotMatch(rules(post({ body })), /no change list/);
});

test('a long bullet list is counted in full', () => {
  // A multiline regex with `$` inside a lookahead truncates each section to
  // its first line, which once reported a nineteen-entry list as two.
  const bullets = Array.from({ length: 19 }, (_, i) => `- change number ${i + 1}`).join('\n');
  const { notes } = validatePost(post({ body: `${FILLER}\n\n${bullets}\n` }));
  assert.ok(notes.some((note) => note.includes('19 real entries')), notes.join('|'));
});

test('a list of nothing but placeholders is not a change list', () => {
  const body = `${FILLER}\n\n- General improvements\n`;
  assert.match(rules(post({ body })), /no change list found/);
});

// -- CLI --------------------------------------------------------------------

function runCli(args, cwd = REPO_ROOT) {
  return spawnSync(process.execPath, [SCRIPT, ...args], { cwd, encoding: 'utf8' });
}

function writeTemp(name, content) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hqci-'));
  const file = path.join(dir, name);
  fs.writeFileSync(file, content, 'utf8');
  return file;
}

test('the CLI exits 0 on a good post', () => {
  const file = writeTemp('good.md', post());
  const result = runCli([file]);
  assert.equal(result.status, 0, result.stderr);
});

test('the CLI exits 1 and explains the failure on stderr', () => {
  const file = writeTemp('bad.md', post({ body: 'Too short.\n' }));
  const result = runCli([file]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /FAIL/);
});

test('the CLI checks every file it is given', () => {
  const good = writeTemp('good.md', post());
  const bad = writeTemp('bad.md', post({ body: 'Too short.\n' }));
  const result = runCli([good, bad]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /bad\.md/);
  assert.doesNotMatch(result.stderr, /good\.md/);
});

test('an unreadable file is a failure, not a crash', () => {
  const result = runCli([path.join(os.tmpdir(), 'definitely-not-here.md')]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /could not read/);
});

test('the CLI reads thresholds from a config file', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hqci-cfg-'));
  const cfg = path.join(dir, '.hugo-quality.json');
  fs.writeFileSync(cfg, JSON.stringify({ generatedPost: { minWordCount: 2 } }), 'utf8');
  const file = path.join(dir, 'short.md');
  fs.writeFileSync(file, post({ body: 'Short.\n\n- one change\n' }), 'utf8');

  assert.equal(runCli([file], dir).status, 0);
  assert.equal(runCli(['--config', cfg, file]).status, 0);
});

test('a missing explicit config is a usage error, not a silent default', () => {
  const file = writeTemp('good.md', post());
  const result = runCli(['--config', '/nope/.hugo-quality.json', file]);
  assert.equal(result.status, 2);
});

test('the repository default config parses and drives the CLI', () => {
  const file = writeTemp('good.md', post());
  const result = runCli(['--config', path.join(REPO_ROOT, '.hugo-quality.json'), file]);
  assert.equal(result.status, 0, result.stderr);
});

test('the CLI still runs when its own path contains a space', () => {
  // The entry-point guard compares the script path against argv[1]. Comparing
  // a percent-encoded file: URL against a filesystem path never matches once
  // the path holds a space, so main() silently never ran and every check
  // "passed" — the exact green-over-nothing failure this repo exists to catch.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hqci dir '));
  const script = path.join(dir, 'validate-generated-post.js');
  fs.copyFileSync(SCRIPT, script);
  // The copy leaves the package behind, so mark the temp dir as ESM. Without
  // this Node 18 loads the copy as CommonJS and dies on `import` before the
  // entry-point guard under test ever runs.
  fs.writeFileSync(path.join(dir, 'package.json'), '{"type":"module"}\n', 'utf8');
  const file = path.join(dir, 'bad.md');
  fs.writeFileSync(file, post({ body: 'Too short.\n' }), 'utf8');

  const result = spawnSync(process.execPath, [script, file], { cwd: dir, encoding: 'utf8' });
  assert.equal(result.status, 1, `expected a failure, got ${result.status}: ${result.stdout}`);
  assert.match(result.stderr, /FAIL/);
});
