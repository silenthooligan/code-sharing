# fliphtml5-liberator

Command-line extractor for FlipHTML5 books. Resolves the page manifest,
downloads page images at the highest available resolution, and
assembles them into a single PDF.

FlipHTML5 publishes books as JavaScript-driven flipbook viewers backed
by a `config.js` file that lists the pages. Recent / "Protected"
deployments obfuscate that page list with an Emscripten-compiled
WebAssembly binary (`deString.wasm`) loaded by `deString.js`. This tool
handles both layouts.

## Capabilities

| Capability | Status |
|---|---|
| Plain `config.js` (page list exposed in source) | ✅ Direct extraction, no Node.js needed |
| Encrypted / "Protected" `config.js` (WASM-decoded) | ✅ Via host-environment polyfill in Node.js |
| Nested encryption (page list itself an encrypted blob) | ✅ Recursive WASM decode |
| Hashed image filenames (`/files/large/<hash>.webp`) | ✅ Resolved from manifest |
| Concurrent page downloads | ✅ `httpx.AsyncClient` + `asyncio.gather` |
| WebP and JPEG inputs | ✅ Auto-detected; WebP converted via Pillow before PDF assembly |
| PDF output | ✅ Single `book.pdf` via `img2pdf` |

## How extraction works

The downloader runs in two stages.

### Stage 1: Manifest extraction

Fetches `https://online.fliphtml5.com/<book_id>/javascript/config.js`
(falling back to `/config.js`) and tries the plain-text path first:

1. **Plain path.** Regex search for the `fliphtml5_pages = [...]`
   assignment. If present, the JavaScript object literal is normalized
   to JSON and parsed directly. No subprocess required.
2. **WASM path.** If the page list is absent or stored as an encrypted
   string, the script spawns `node fliphtml5_decoder.js <config_path>`
   and reads the decrypted manifest from stdout.

The Node.js helper performs the decryption inside a host-environment
polyfill so the original WASM binary runs unmodified:

- Loads `deString.wasm` as a binary buffer.
- Patches `deString.js` to remove the inlined data URI loader and
  replaces the `Module.onRuntimeInitialized` callback so initialization
  resolves a Promise.
- Reimplements `stringToUTF8` and `UTF8ToString` against the WASM heap
  because the upstream exports are typically stripped or mangled.
- Evaluates the original `config.js` to materialize whatever `bookConfig`
  / `htmlConfig` globals it defines.
- Calls the exported `_DeString()` to decrypt `bookConfig` and the
  `fliphtml5_pages` string.
- Detects nested encryption (decoded payload starting with the `v`
  signature) and re-runs `_DeString()` until the result parses as JSON.

The decrypted manifest is written to stdout and consumed by Python.

### Stage 2: Page download and PDF assembly

For each page entry in the manifest, the script resolves an image URL
using the entry's `l` (link) or `n` (number) field:

- Absolute URLs are used as-is.
- Paths starting with `files/` are prefixed with
  `http://online.fliphtml5.com/<book_id>/`.
- Bare hash-style filenames are placed under
  `http://online.fliphtml5.com/<book_id>/files/large/<filename>`, which
  is the highest-resolution variant FlipHTML5 publishes.

Pages are downloaded concurrently with a 15-second per-request timeout
via `httpx.AsyncClient`. Failed pages are logged as warnings and
skipped (the resulting PDF will be missing those pages rather than
aborting the entire run). WebP responses are converted to PNG with
Pillow before `img2pdf.convert()` writes `book.pdf`.

## Prerequisites

- **Python 3.7+**
- **Node.js** (any recent LTS) for the WASM decoder path. Not required
  if every book you process exposes its page list in plain `config.js`.
- **`deString.js` and `deString.wasm`** from the target book, placed in
  the project root. These are not bundled because they are the book
  publisher's binaries and may vary between FlipHTML5 deployments.

### Acquiring `deString.js` and `deString.wasm`

1. Open the target book in a browser.
2. Open DevTools (F12) and switch to the **Network** tab.
3. Reload the page.
4. Filter requests for `deString`.
5. Right-click each of `deString.js` and `deString.wasm` and save them
   into the `fliphtml5-liberator/` directory next to `downloader.py`.

The same pair generally works across books published by the same
FlipHTML5 account version. If decoding fails on a new book, refresh
the binaries from that book's network trace.

## Installation

```bash
git clone https://github.com/silenthooligan/code-sharing.git
cd code-sharing/fliphtml5-liberator

pip install httpx img2pdf Pillow
```

There is no `requirements.txt`; the dependency surface is small and
stable. Pin manually if reproducibility matters to you.

## Usage

```bash
python downloader.py <book_url_or_id>
```

Either a full URL or just the `<account>/<book>` ID portion is
accepted:

```bash
python downloader.py https://online.fliphtml5.com/ousx/stby
python downloader.py ousx/stby
```

Output goes to `book.pdf` in the current working directory.
Intermediate image files are written to a temp directory that is
cleaned up on exit. Logs go to stdout in `LEVELNAME: message` format.

## Operational notes

- **Output filename is hardcoded.** Each run overwrites `book.pdf` in
  the current directory. Run from a per-book working directory or
  rename after each invocation.
- **Non-ASCII `config.js`.** Some books ship `config.js` with
  non-ASCII bytes (often book metadata in CJK or accented Latin). The
  downloader reads with `errors='replace'` so this no longer aborts
  with `UnicodeDecodeError`; the regex matchers operate on the
  replaced text and find the page-list assignment unchanged.
- **WASM path is skipped automatically** when the plain page list is
  present, avoiding subprocess overhead for the common case.
- **Hashed filenames may 404** if the book uses a non-standard storage
  layout. The warning is logged and the page is skipped; inspect the
  manifest entry to see whether the `l` field contains a usable
  fallback path.
- **Concurrency is unbounded.** `asyncio.gather` issues all page
  requests in parallel. For large books on slow links, consider
  patching `download_image` to use a `Semaphore`.

## Disclaimer

For educational and personal-archival use only. Respect the copyright
and terms of service of any content you process. Do not redistribute
copyrighted material without permission from the rights holder.

## License

[MIT](../LICENSE).
