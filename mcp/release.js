// Load a release built by scripts/hosted_release.py and verify every file
// against manifest.json before anything is served. Pure ESM; runs in the
// Cloudflare Worker (bytes from env.ASSETS) and in Node (bytes from disk).
//
// Fail-closed contract (design §1.4): a file whose SHA-256 does not match the
// manifest, or that is missing, is never served. Reading it throws a
// ReleaseIntegrityError that names the path and the reason — never the
// content. get_release reports the failed paths so the condition is visible.

export class ReleaseIntegrityError extends Error {
  constructor(path, reason) {
    super(`release file unavailable: ${path} (${reason})`);
    this.name = 'ReleaseIntegrityError';
    this.path = path;
    this.reason = reason;
  }
}

const HEX = Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, '0'));

export async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const view = new Uint8Array(digest);
  let out = '';
  for (let i = 0; i < view.length; i++) out += HEX[view[i]];
  return out;
}

const decoder = new TextDecoder('utf-8');

export class Release {
  /**
   * @param {object} manifest parsed manifest.json
   * @param {Map<string, Uint8Array>} files verified bytes by release path
   * @param {{path: string, reason: string}[]} failed files that did not verify
   */
  constructor(manifest, files, failed, manifestSha256 = null) {
    this.manifest = manifest;
    this.files = files;
    this.failed = failed;
    this.manifestSha256 = manifestSha256;
    this.parsed = new Map();
  }

  get integrity() {
    return { ok: this.failed.length === 0, failed: this.failed.map((f) => ({ ...f })) };
  }

  has(path) {
    return this.files.has(path);
  }

  meta(path) {
    return this.manifest.files?.[path] ?? null;
  }

  bytes(path) {
    const b = this.files.get(path);
    if (b) return b;
    const failure = this.failed.find((f) => f.path === path);
    if (failure) throw new ReleaseIntegrityError(path, failure.reason);
    throw new ReleaseIntegrityError(path, 'not in the release manifest');
  }

  text(path) {
    return decoder.decode(this.bytes(path));
  }

  json(path) {
    if (this.parsed.has(path)) return this.parsed.get(path);
    const value = JSON.parse(this.text(path));
    this.parsed.set(path, value);
    return value;
  }

  /** Paths in the manifest under a prefix, in manifest order. */
  list(prefix) {
    return Object.keys(this.manifest.files ?? {}).filter((p) => p.startsWith(prefix));
  }
}

/**
 * Load and verify a release.
 * @param {(path: string) => Promise<Uint8Array|null>} fetchBytes
 */
export async function loadRelease(fetchBytes) {
  const manifestBytes = await fetchBytes('manifest.json');
  if (!manifestBytes) throw new ReleaseIntegrityError('manifest.json', 'missing');
  let manifest;
  try {
    manifest = JSON.parse(decoder.decode(manifestBytes));
  } catch {
    throw new ReleaseIntegrityError('manifest.json', 'not valid JSON');
  }
  if (!manifest || typeof manifest.files !== 'object' || !manifest.library_release) {
    throw new ReleaseIntegrityError('manifest.json', 'not a hosted release manifest');
  }
  const files = new Map();
  const failed = [];
  await Promise.all(
    Object.entries(manifest.files).map(async ([path, meta]) => {
      const bytes = await fetchBytes(path);
      if (!bytes) {
        failed.push({ path, reason: 'missing' });
        return;
      }
      const hash = await sha256Hex(bytes);
      if (hash !== meta?.sha256) {
        failed.push({ path, reason: 'sha256 does not match the manifest' });
        return;
      }
      files.set(path, bytes);
    }),
  );
  failed.sort((a, b) => a.path.localeCompare(b.path));
  return new Release(manifest, files, failed, await sha256Hex(manifestBytes));
}

/** Fetch release files from a Worker static-assets binding. */
export function assetsFetcher(assets) {
  return async (path) => {
    const res = await assets.fetch(`https://assets.local/${encodeURI(path)}`);
    if (!res.ok) return null;
    return new Uint8Array(await res.arrayBuffer());
  };
}

/** Fetch release files from a directory on disk (Node only). */
export async function directoryFetcher(dir) {
  const { readFile } = await import('node:fs/promises');
  const { join, resolve, sep } = await import('node:path');
  const root = resolve(dir);
  return async (path) => {
    const full = resolve(join(root, path));
    if (!full.startsWith(root + sep) && full !== root) return null;
    try {
      return new Uint8Array(await readFile(full));
    } catch {
      return null;
    }
  };
}
