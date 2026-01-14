const nodeFS = require('fs');
const path = require('path');

// Logging helper to stderr
function log(msg) {
    console.error(`[Decoder] ${msg}`);
}

// ----------------------------------------------------------------------
// Local Polyfills (Replacements for Emscripten internals)
// ----------------------------------------------------------------------
function localStringToUTF8(str, outPtr, maxBytesToWrite) {
    if (!(maxBytesToWrite > 0)) return 0;
    let startPtr = outPtr;
    let endPtr = startPtr + maxBytesToWrite - 1;
    for (let i = 0; i < str.length; ++i) {
        let u = str.charCodeAt(i);
        if (outPtr + 1 < endPtr) {
            Module.HEAPU8[outPtr++] = u;
        }
    }
    Module.HEAPU8[outPtr] = 0;
}

function localUTF8ToString(ptr) {
    if (!Module.HEAPU8) return "HEAPU8 not ready";
    let str = '';
    let idx = ptr;
    while (true) {
        let char = Module.HEAPU8[idx++];
        if (char === 0) break;
        str += String.fromCharCode(char);
    }
    return str;
}

// ----------------------------------------------------------------------
// Module Configuration
// ----------------------------------------------------------------------
global.Module = {
    wasmBinary: nodeFS.readFileSync(path.join(__dirname, 'deString.wasm')),
    onRuntimeInitialized: function () {
        log("WASM Runtime initialized.");
        ensurePolyfills();
        runLogic();
    },
    onAbort: function (what) { log("Aborted: " + what); },
    print: function (text) { log("Module stdout: " + text); },
    printErr: function (text) { log("Module stderr: " + text); }
};

function ensurePolyfills() {
    log("Injecting polyfills...");
    Module.stringToUTF8 = localStringToUTF8;
    Module.UTF8ToString = localUTF8ToString;
    if (!Module._malloc && Module.asm) Module._malloc = Module.asm._malloc || Module.asm.malloc;
    if (!Module._free && Module.asm) Module._free = Module.asm._free || Module.asm.free;
}

// ----------------------------------------------------------------------
// Main Decoding Logic
// ----------------------------------------------------------------------
function runLogic() {
    log("Starting execution logic...");
    try {
        const inputFile = process.argv[2];
        if (!inputFile || !nodeFS.existsSync(inputFile)) {
            log(`File not found: ${inputFile}`);
            process.exit(1);
        }

        let content = nodeFS.readFileSync(inputFile, 'utf8');
        global.htmlConfig = {};
        global.fliphtml5_pages = [];
        global.window = {};

        // 1. Try Global Eval to capture variables like 'var fliphtml5_pages = ...'
        try {
            // Indirect eval to execute in global scope
            (0, eval)(content);
        } catch (e) {
            log("Eval error (continuing with regex): " + e);
        }

        // 2. Regex fallbacks if eval missed them
        if (!global.fliphtml5_pages || global.fliphtml5_pages.length === 0) {
            const pagesMatch = content.match(/var\s+fliphtml5_pages\s*=\s*(\[[\s\S]*?\]);/);
            if (pagesMatch) {
                try {
                    global.fliphtml5_pages = JSON.parse(pagesMatch[1]);
                } catch (e) {
                    try { global.fliphtml5_pages = eval(pagesMatch[1]); } catch (e2) { }
                }
            }
        }

        if (!global.htmlConfig || Object.keys(global.htmlConfig).length === 0) {
            const configMatch = content.match(/var\s+htmlConfig\s*=\s*(\{[\s\S]*?\});/);
            if (configMatch) {
                try {
                    global.htmlConfig = eval("(" + configMatch[1] + ")");
                } catch (e) { }
            }
        }

        // Legacy/Protected fallback: just the bookConfig string
        if (!global.htmlConfig || !global.htmlConfig.bookConfig) {
            const match3 = content.match(/bookConfig"\s*:\s*"([^"]+)"/);
            if (match3) {
                if (!global.htmlConfig) global.htmlConfig = {};
                global.htmlConfig.bookConfig = match3[1];
            }
        }

        // 3. Decrypt bookConfig if needed
        let finalConfig = global.htmlConfig || {};

        if (finalConfig.bookConfig && typeof finalConfig.bookConfig === 'string') {
            log("Found encrypted bookConfig. Decoding...");
            const decodedStr = runDeString(finalConfig.bookConfig);
            try {
                const decodedObj = JSON.parse(decodedStr);
                finalConfig = { ...finalConfig, ...decodedObj };
                log("Merged decoded config.");
            } catch (e) {
                log("Failed to parse decoded bookConfig: " + e);
            }
        }

        // 4. Merge fliphtml5_pages into final result if not present
        if (global.fliphtml5_pages && global.fliphtml5_pages.length > 0) {
            finalConfig.fliphtml5_pages = global.fliphtml5_pages;
        }

        // Check if fliphtml5_pages is an encrypted string (nested encryption)
        if (finalConfig.fliphtml5_pages) {
            const pagesVal = finalConfig.fliphtml5_pages;
            const isString = typeof pagesVal === 'string';

            if (isString && pagesVal.startsWith('v')) {
                log("fliphtml5_pages seems to be encrypted string. Decoding...");
                try {
                    const decodedPages = runDeString(pagesVal);
                    try {
                        finalConfig.fliphtml5_pages = JSON.parse(decodedPages);
                        log("Successfully decoded fliphtml5_pages.");
                    } catch (e) {
                        log("JSON parse failed for pages. Trying to clean trailing junk...");
                        try {
                            const lastBrace = decodedPages.lastIndexOf(']');
                            if (lastBrace !== -1) {
                                const cleanPages = decodedPages.substring(0, lastBrace + 1);
                                finalConfig.fliphtml5_pages = JSON.parse(cleanPages);
                                log("Successfully decoded fliphtml5_pages AFTER CLEANING.");
                            } else {
                                throw e;
                            }
                        } catch (e2) {
                            finalConfig._pagesDecodingError = "Parse failed: " + e + " | Clean failed: " + e2;
                        }
                    }
                } catch (e) {
                    log("Failed to decode fliphtml5_pages: " + e);
                    finalConfig._pagesDecodingError = "DeString failed: " + e;
                }
            } else if (isString) {
                finalConfig._pagesTypeInfo = "String: " + pagesVal.substring(0, 50);
            }
        }

        // 5. Output
        if (finalConfig.bookConfig) delete finalConfig.bookConfig;
        const outputStr = JSON.stringify(finalConfig);
        process.stdout.write(outputStr, () => {
            log("Success.");
            process.exit(0);
        });

    } catch (e) {
        log("Error executing logic: " + e);
        process.exit(1);
    }
}

function runDeString(input) {
    const len = input.length * 4 + 1;

    if (!Module._malloc) {
        if (Module.asm && Module.asm.malloc) Module._malloc = Module.asm.malloc;
        else if (Module.asm && Module.asm._malloc) Module._malloc = Module.asm._malloc;
        else throw new Error("Module._malloc is missing.");
    }

    const ptr = Module._malloc(len);
    localStringToUTF8(input, ptr, len);

    const deStringFn = Module._DeString || (Module.asm ? Module.asm.DeString : null) || global._DeString;
    if (typeof deStringFn !== 'function') throw new Error("_DeString not found.");

    // Invoke WASM function
    const resPtr = deStringFn(ptr);
    const result = localUTF8ToString(resPtr);

    if (Module._free) Module._free(ptr);
    return result;
}

// ----------------------------------------------------------------------
// Load and Patch deString.js
// ----------------------------------------------------------------------
log("Loading deString.js...");
let jsContent = nodeFS.readFileSync(path.join(__dirname, 'deString.js'), 'utf8');

// Patch 1: Prevent overwriting onRuntimeInitialized
const patchInitRegex = /Module\.onRuntimeInitialized\s*=\s*function\(\)\s*\{Module\.isReady\s*=\s*true;?\}/g;
if (patchInitRegex.test(jsContent)) jsContent = jsContent.replace(patchInitRegex, "/* patched out */");
else if (jsContent.includes("Module.onRuntimeInitialized = function() {Module.isReady = true;}")) jsContent = jsContent.replace("Module.onRuntimeInitialized = function() {Module.isReady = true;}", "/* patched out */");

// Patch 2: Strip hardcoded Data URI to prevent ENAMETOOLONG errors
const dataUriSignature = "data:application/octet-stream;base64,AGFzb";
let dataUriStart = jsContent.indexOf(dataUriSignature);
if (dataUriStart !== -1) {
    let quoteChar = jsContent[dataUriStart - 1];
    let dataUriEnd = jsContent.indexOf(quoteChar, dataUriStart);
    if (dataUriEnd !== -1) {
        let before = jsContent.substring(0, dataUriStart - 1);
        let after = jsContent.substring(dataUriEnd + 1);
        jsContent = before + '"deString.wasm"' + after;
        log("Patch applied: Replaced Data URI.");
    }
}

try { eval(jsContent); } catch (e) { log("Error evaluating deString.js: " + e); }

setTimeout(() => {
    if (Module.asm) {
        log("Polled readiness.");
        ensurePolyfills();
        runLogic();
    } else {
        log("Timeout.");
        process.exit(1);
    }
}, 1500);
