#!/usr/bin/env node
/**
 * Validate a generated content file before it is merged.
 *
 * Release notes, changelog pages and other machine-written posts fail in a
 * particular way: the generator runs, exits 0, and writes a page that is
 * structurally fine and editorially empty. The shapes this catches, all of
 * them observed in practice:
 *
 *   1. placeholder rows the generator emits when its input list was empty
 *      ("General improvements | See release notes");
 *   2. a description field that trails off ("... adds .") because no entries
 *      were parsed;
 *   3. raw commit SHAs dumped into a summary field when the generator fell
 *      back to raw log output;
 *   4. a body too short to be a real post;
 *   5. no change list at all.
 *
 * Thresholds and phrases come from .hugo-quality.json (see the README); with
 * no config file the defaults below apply.
 *
 * Usage:
 *   node validate-generated-post.js <file.md> [<file.md> ...]
 *   node validate-generated-post.js --config path/to/.hugo-quality.json <file.md>
 *
 * Exit 0 = every file passes. Exit 1 = at least one failed (reasons on stderr).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DEFAULTS = {
  minWordCount: 100,
  placeholderPhrases: ['General improvements', 'See release notes', 'Lorem ipsum'],
  emptyDescriptionPatterns: ['^\\s*$', '\\b(?:adds|includes|contains|covers)\\s*\\.?\\s*$'],
  shaFreeFields: ['summary', 'description'],
  requireChangeList: true,
};

function parseArgs(argv) {
  const files = [];
  let configPath = null;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--config') {
      configPath = argv[i + 1];
      i += 1;
    } else if (argv[i] === '--help' || argv[i] === '-h') {
      return { help: true, files, configPath };
    } else {
      files.push(argv[i]);
    }
  }
  return { help: false, files, configPath };
}

function loadConfig(configPath) {
  const target = configPath || path.join(process.cwd(), '.hugo-quality.json');
  if (!fs.existsSync(target)) {
    if (configPath) {
      process.stderr.write(`Config file not found: ${target}\n`);
      process.exit(2);
    }
    return { ...DEFAULTS };
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(target, 'utf8'));
  } catch (err) {
    process.stderr.write(`Could not parse ${target}: ${err.message}\n`);
    process.exit(2);
  }
  return { ...DEFAULTS, ...(parsed.generatedPost || {}) };
}

/** Split a document into its front-matter source and its body. */
function splitDocument(content) {
  const match = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(content);
  if (!match) return { frontmatter: '', body: content };
  return { frontmatter: match[1], body: match[2] };
}

/**
 * Read one scalar field out of the front matter.
 *
 * Deliberately a line scan and not a YAML parse: this script is stdlib-only so
 * it can be copied into any site without adding a dependency, and every field
 * it reads is a quoted or bare scalar on one line.
 */
function frontmatterField(frontmatter, field) {
  const pattern = new RegExp(`^${field}:\\s*(.*)$`, 'm');
  const match = pattern.exec(frontmatter);
  if (!match) return null;
  return match[1].trim().replace(/^["'](.*)["']$/, '$1');
}

/**
 * Collect the change entries in a post body.
 *
 * Two shapes are accepted because generators and humans write differently and
 * an archive outlives a format change:
 *
 *   - one-line bullets, grouped under whatever headings the author chose.
 *     Requiring specific headings punishes hand-written posts that group
 *     changes by theme rather than by "Features"/"Fixes".
 *   - a markdown change table, which older generators emitted.
 *
 * The bullets are gathered with a line scan rather than a multiline regex: with
 * the `m` flag a `$` inside a lookahead matches every line ending, which
 * silently truncates each section to its first line and undercounts a
 * nineteen-entry list as two.
 */
function collectChangeBullets(body, placeholderPhrases) {
  return body
    .split('\n')
    .map((line) => line.trim())
    .filter(
      (line) =>
        (line.startsWith('- ') || line.startsWith('* ')) &&
        line.length > 2 &&
        !placeholderPhrases.some((phrase) => line.includes(phrase)),
    );
}

function collectTableRows(body, placeholderPhrases) {
  const match = /\|[^\n]*\|\n\|[-| :]+\|\n([\s\S]+?)(?:\n\n|\n---|\n#{2,}|$)/.exec(body);
  if (!match) return null;
  return match[1]
    .split('\n')
    .filter(
      (line) =>
        line.trim().startsWith('|') &&
        !placeholderPhrases.some((phrase) => line.includes(phrase)),
    );
}

/**
 * Validate one document.
 *
 * @returns {{failures: string[], notes: string[]}}
 */
export function validatePost(content, cfg = DEFAULTS) {
  const failures = [];
  const notes = [];
  const { frontmatter, body } = splitDocument(content);
  const placeholders = cfg.placeholderPhrases || [];

  // 1. placeholder text left behind by an empty generator input
  const foundPlaceholders = placeholders.filter((phrase) => content.includes(phrase));
  if (foundPlaceholders.length > 0) {
    failures.push(
      `contains placeholder text ${JSON.stringify(foundPlaceholders)} — the generator ` +
        'ran with an empty change list',
    );
  } else {
    notes.push('no placeholder text');
  }

  // 2. a description that trails off
  const description = frontmatterField(frontmatter, 'description');
  if (description !== null) {
    const offender = (cfg.emptyDescriptionPatterns || []).find((pattern) =>
      new RegExp(pattern, 'i').test(description),
    );
    if (offender) {
      failures.push(
        `description is effectively empty (${JSON.stringify(description)}) — no entries ` +
          'were parsed when the post was generated',
      );
    } else {
      notes.push('description is non-empty');
    }
  }

  // 3. raw commit SHAs in a prose field
  for (const field of cfg.shaFreeFields || []) {
    const value = frontmatterField(frontmatter, field);
    if (value && /\b[0-9a-f]{7,40}\b/.test(value)) {
      failures.push(
        `${field} contains a raw commit SHA — the field was set from raw log output`,
      );
    } else if (value) {
      notes.push(`${field} has no raw commit SHAs`);
    }
  }

  // 4. body length
  const wordCount = body.trim().split(/\s+/).filter(Boolean).length;
  const minWords = cfg.minWordCount ?? DEFAULTS.minWordCount;
  if (wordCount < minWords) {
    failures.push(`body is ${wordCount} words, minimum ${minWords} — the post has no real content`);
  } else {
    notes.push(`body word count: ${wordCount}`);
  }

  // 5. at least one real change entry
  if (cfg.requireChangeList) {
    const rows = collectTableRows(body, placeholders);
    const bullets = collectChangeBullets(body, placeholders);
    if (rows && rows.length > 0) {
      notes.push(`change table has ${rows.length} real entries`);
    } else if (bullets.length > 0) {
      notes.push(`change list has ${bullets.length} real entries`);
    } else {
      failures.push('no change list found — expected bullet entries or a change table');
    }
  }

  return { failures, notes };
}

function main() {
  const { help, files, configPath } = parseArgs(process.argv.slice(2));
  if (help || files.length === 0) {
    process.stderr.write(
      'Usage: validate-generated-post.js [--config <file>] <file.md> [<file.md> ...]\n',
    );
    process.exit(files.length === 0 && !help ? 1 : 0);
  }

  const cfg = loadConfig(configPath);
  let failed = false;

  for (const file of files) {
    let content;
    try {
      content = fs.readFileSync(file, 'utf8');
    } catch (err) {
      process.stderr.write(`FAIL: ${file} — could not read: ${err.message}\n`);
      failed = true;
      continue;
    }

    const { failures, notes } = validatePost(content, cfg);
    for (const note of notes) process.stdout.write(`  OK: ${file} — ${note}\n`);
    for (const failure of failures) process.stderr.write(`FAIL: ${file} — ${failure}\n`);
    if (failures.length > 0) failed = true;
  }

  process.exit(failed ? 1 : 0);
}

// Only run when invoked directly, so the checks stay importable from tests.
// fileURLToPath, not URL.pathname: pathname is percent-encoded, so a script
// living under a path with a space would never match argv[1], main() would
// never run, and the CLI would exit 0 having checked nothing.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
