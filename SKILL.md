---
name: humanly
description: >
  Transforms AI-generated or messy code into clean, human-readable code with
  proper structure, meaningful names, and purposeful comments. Use this skill
  whenever the user asks to "clean up code", "make code more readable", "add
  comments", "humanize code", "remove AI smell", "refactor for clarity", or
  says code looks AI-generated or hard to understand. Also trigger when the
  user shares code that shows AI anti-patterns: generic names (data, result,
  helper), banner comments compensating for missing structure, mid-function
  imports, over-commented obvious lines, or flat procedural blocks that should
  be extracted. Works across Python, C++, JavaScript/TypeScript, and config
  files. Supports two modes: review (annotated feedback) and rewrite (clean
  output). Always trigger this skill when the user's goal is code clarity,
  not correctness or performance.
---

# Humanly

Transform code from AI-generated or messy to genuinely human-readable.

## Core Principle

**The goal is lower time-to-understanding, not shorter or longer code.**

A rewrite will often produce more lines than the original. That is fine —
and expected — as long as every added line reduces the time a reader needs
to understand the code. A 140-line file that a new developer understands in
2 minutes is better than an 80-line file that takes 20 minutes and a Slack
message to the author.

The inverse is also true: comments that describe what the code already says
clearly, docstrings on trivial functions, and extracted functions that are
shallower than their own signature — these add lines without reducing
comprehension. They are noise and should be removed.

The test for every addition:
> *Does this save a future reader meaningful time or prevent a real mistake?*
> If yes — add it. If no — cut it.

Fix structure first; add comments only where structure alone can't explain
intent.

---

## Two Modes

Always clarify which mode the user wants before starting. If unclear, ask.

### Review Mode
Output annotated feedback. Explain *what* to change and *why*. Do not rewrite
the code. Good for learning, code review, and understanding issues before
committing to changes.

Review mode **can suggest creating new methods or helpers** that don't exist
yet — these are recommendations for the developer to implement, not changes
Humanly makes itself.

Format each issue as:
```
[SEVERITY] Line X — <issue>
Why: <explanation>
Fix: <concrete suggestion>
```

### Rewrite Mode
Output the cleaned version directly. Preserve all behavior — never change
logic, algorithms, or side effects. Strictly structural and documentary
changes only.

**Rewrite mode only touches what already exists.** It does not create new
methods, classes, or helpers in other files. If a change would require
creating code outside the file being rewritten, flag it as a `# NOTE:`
comment inline and mention it in the summary — but do not implement it.

```python
# NOTE: consider adding sgie_interval_is_enabled() to PipelineConfig —
# would make this condition read as a domain concept instead of arithmetic.
# Until then, the intent is: sgie_interval < 0 means disabled.
if cfg.sgie_interval >= 0:
```

**Always open with a branch recommendation.** Every rewrite output starts
with this block before the code:

```
⚠️ Before applying this rewrite, create a branch:
git checkout -b humanly/refactor
```

If the rewrite includes any high-risk changes (function extraction, symbol
rename, error handling changes, middleware reorder), upgrade the warning:

```
⚠️ This rewrite includes structural changes that carry runtime risk
(function extraction / symbol rename / error handling change).
Strongly recommend a branch and running your test suite before merging:

git checkout -b humanly/refactor
# apply changes
python -m pytest
```

Always add a short summary at the end noting what changed and why.

---

## Severity Levels

Use these consistently in both modes:

- 🔴 **REWRITE** — Structure is wrong. Flat block needs extraction, function
  does multiple things, or the shape of the code actively hides intent.
- 🟡 **RENAME** — Names are generic, misleading, or don't reflect domain
  vocabulary.
- 🟢 **ANNOTATE** — Structure and names are fine; a comment or docstring would
  help a future reader.

---

## Before You Start: Identify the Domain Narrative

Before rewriting anything, read the code and ask:

> **What is the natural sequence of steps this domain follows?**

The answer comes from the library or problem domain, not from generic software
patterns. A few examples:

| Domain | Natural narrative |
|---|---|
| GStreamer / DeepStream | build primary elements → build secondary elements → link pipeline |
| PyTorch training | load data → build model → train loop → evaluate |
| FastAPI / web backend | define models → define routes → register middleware |
| ROS 2 node | declare parameters → create pub/sub → register callbacks |
| Odoo module | define models → define views → define access rules |

Once you identify the narrative, use it as the skeleton of the rewrite. The
top-level function should read like a table of contents for that sequence —
a reader skimming it should understand the full flow without jumping anywhere.

**If you can't identify a natural narrative**, ask the user before rewriting.
A wrong skeleton is worse than no skeleton.

---

## File Types and Their Rules

Not all files have the same shape. Before applying rules, identify what kind
of file you're looking at — the standards differ.

### Logic files (most files)
Functions, classes, business logic. Apply all Core Rules fully: extract
functions, avoid banner comments, prefer structure over comments.

### Entrypoints and configuration files
Files whose job is to *register* things rather than *do* things — FastAPI
`main.py`, Django `settings.py`, ROS 2 node constructors, Odoo `__manifest__`,
GStreamer pipeline builders. These have different rules:

- **Banner comments are acceptable** — the file is inherently linear and
  flat by design. Sections like `# ── Middleware ──` help navigation without
  implying missing structure.
- **The problem is usually missing comments, not missing functions** — the
  reader needs to understand *why* each registration decision was made, not
  *what* is being registered (that's already obvious).
- **Document non-obvious decisions explicitly:**
  - Middleware registration order (FastAPI applies in reverse — CORS must
    run first so it goes last in code)
  - `wait=False` / `wait=True` on shutdown calls
  - Why docs are disabled in production
  - Why an import is deferred inside the lifespan/startup handler
  - Gotchas like double-prefixing on routers
- **Module-level docstring is required** — explain what the file is, what
  the ASGI/entry object is, and any non-obvious wiring (e.g. Socket.IO
  wrapping FastAPI).
- **Registration order comments** — if order matters (middleware, signal
  handlers, plugin loading), always document the actual execution order and
  why it is what it is.

---

## Core Rules

### Structure
- **Extract named functions — but only when justified.** A function earns its
  place when at least one of these is true:
  - Its name reveals intent the code doesn't reveal on its own
  - It can fail independently and deserves its own error context
  - It's reused in more than one place
  - It hides an implementation detail that could change
  - Without it, the parent function doesn't fit on one screen
  
  Do not extract just to reduce line count. Shallow functions (more
  signature/docstring than body) add indirection without value.
- **Imports at the top — but check before moving conditional ones.**
  The default rule: all imports at the top of the file, ordered
  stdlib → third-party → local, one blank line between groups.
  
  However, imports inside conditionals are sometimes intentional. Before
  moving one, ask why it's there. Legitimate reasons to leave it in place:
  - **Optional dependency** — the package may not be installed in all
    environments (e.g. a QA-only or dev-only library). Moving it to the
    top forces every environment to have it.
  - **Circular import resolution** — deferring inside a function is
    sometimes the only practical fix without restructuring the project.
  - **Plugin / dynamic loading** — frameworks like Django, Odoo, and ROS 2
    load modules by string name at runtime; the import is inherently
    conditional.
  - **Startup time** — CLI tools sometimes defer heavy imports so the
    process starts fast.

  If the conditional import is legitimate, leave it and add a comment
  explaining why:
  ```python
  if _IS_QA_ENABLED:
      # Deferred — MjpegServer is a QA-only dependency, not installed
      # in production builds. Import here to avoid forcing it on all envs.
      from mjpeg_server import MjpegServer
  ```

  If the codebase is large enough, suggest extracting QA/optional code
  into its own module and importing the module conditionally instead —
  cleaner than a mid-function import, same effect.
- **Prefer early returns and guard clauses** over nested conditionals. Flat is
  better than nested.
- **One screen per function** — if a function doesn't fit on one screen it
  likely does more than one thing. Split it.
- **Two responsibilities = two functions** — if you need "and" to describe
  what a function does, split it.

### Naming
- **Magic numbers need a name AND a comment explaining the constraint** —
  renaming `320` to `TRACKER_INPUT_WIDTH` is not enough. A reader still
  doesn't know why it's 320 and not 256 or 640. The comment explains the
  constraint, valid range, or consequence of changing it.

  ```python
  # Before — magic number inline, no context
  tracker.set_property("tracker-width", 320)

  # After — named constant with constraint documented
  # Minimum input resolution for nvmultiobjecttracker at this model config.
  # Lower values cause the tracker to lose small/distant objects in crowded scenes.
  TRACKER_INPUT_WIDTH = 320
  tracker.set_property("tracker-width", TRACKER_INPUT_WIDTH)
  ```

  The same applies to sentinel values like `-1` meaning "disabled".
  The treatment depends on mode:

  ```python
  # REWRITE MODE — only add a comment, never create a new method
  # sgie_interval < 0 means disabled — configured per client in config.yaml.
  # NOTE: consider adding cfg.sgie_interval_is_enabled() to PipelineConfig
  # to make this read as a domain concept rather than an arithmetic check.
  if cfg.sgie_interval >= 0:

  # REVIEW MODE — can suggest the new method as a recommendation
  # 🟡 RENAME — Line 12
  # Why: `>= 0` reads as arithmetic. The intent is "is the interval enabled?"
  # Fix: add sgie_interval_is_enabled() to PipelineConfig that encapsulates
  # this check, then replace the condition with cfg.sgie_interval_is_enabled()
  ```
- **Names should reflect domain vocabulary** — ask "what is this thing in
  the language of the problem?" not "what does it do generically?".

  ```python
  # Before — generic CS names
  def process_data(input, result):
      for item in input:
          val = helper(item)
          result.append(val)

  # After — domain names
  def score_detections(raw_frames, scored_detections):
      for frame in raw_frames:
          detection = _run_nvinfer(frame)
          scored_detections.append(detection)
  ```

- **Boolean conditions should read like sentences** — if reading the
  condition out loud sounds like a question, it's good. If it sounds like
  arithmetic, it needs work. How you fix it depends on mode:

  ```python
  # Before — reads as arithmetic, not intent
  if cfg.sgie_interval >= 0 and not cfg.disable_tracker:

  # REWRITE MODE — comment explains intent, NOTE flags the suggestion
  # sgie_interval < 0 = disabled; disable_tracker = True means tracker is off.
  # NOTE: consider cfg.sgie_interval_is_enabled() and cfg.tracker_is_active()
  # on PipelineConfig to make this read as a domain decision.
  if cfg.sgie_interval >= 0 and not cfg.disable_tracker:

  # REVIEW MODE — can suggest the new methods directly
  # 🟡 RENAME — Line 34
  # Why: both conditions read as implementation details, not domain decisions.
  # Fix: add sgie_interval_is_enabled() and tracker_is_active() to
  # PipelineConfig, then replace with:
  #   if cfg.sgie_interval_is_enabled() and cfg.tracker_is_active():
  ```

- **Private helpers use underscore prefix** (Python) — `_create_element()`
  signals internal use without needing a comment.

### Comments

- **Comments explain *why*, not *what*** — the code already says what it
  does. The test: could you derive this comment by just reading the line?
  If yes, delete it. If no, keep it.

  ```python
  # Bad — describes what the code does (obvious from reading it)
  # Loop through capabilities and create nvinfer elements
  for cap in cfg.active_sgies():

  # Bad — restates the condition
  # Check if sgie_interval is greater than or equal to zero
  if cfg.sgie_interval >= 0:

  # Good — explains a non-obvious decision
  # Python-worker capability — no GStreamer element needed here.
  # These caps are handled downstream by the probe thread.
  if cfg_path is None:
      continue

  # Good — explains why this specific value
  # wait=False avoids blocking the process during rolling deploys.
  # Jobs are idempotent and will re-run on the next cycle.
  scheduler.shutdown(wait=False)
  ```

- **No banner comments compensating for missing structure** — if a block
  needs a `# ── Section ──` header to be navigable, it should be a
  function. Exception: entrypoint/config files where flat structure is
  intentional (see File Types section).

- **Flag ambiguous fallback logic** — a silent `continue`, `return None`,
  or `pass` is ambiguous when it could mean either "this is expected and
  fine" or "this is an error we're swallowing". Make the intent explicit.

  ```python
  # Ambiguous — is this an error or expected behavior?
  if cfg_path is None:
      continue

  # Clear — comment explains it's intentional
  if cfg_path is None:
      # Python-worker capability — skipping is correct, not an error.
      logger.info("Skipping SGIE for '%s': handled by Python worker", cap)
      continue
  ```

- **Docstring depth matches function complexity.** Three tiers:

  ```python
  # Tier 1 — No docstring. Name says everything.
  def sgie_interval_is_enabled(self) -> bool:
      return self.sgie_interval >= 0

  # Tier 2 — One line. Adds something the name doesn't.
  def active_sgies(self) -> list[str]:
      """Return capabilities that require a GStreamer inference element."""
      return [cap for cap in self.pipeline if cap in SGIE_CONFIGS]

  # Tier 3 — Full docstring. Has side effects, can fail, or parameters
  # need explanation.
  def build_sgie_elements(cfg: PipelineConfig) -> list[Gst.Element]:
      """Instantiate one nvinfer SGIE element per active capability.

      Capabilities backed by Python workers are skipped — they don't use
      a GStreamer inference element and are handled downstream by probes.

      Args:
          cfg: Pipeline config with active capability list and sgie interval.

      Returns:
          List of configured nvinfer Gst.Elements, one per GStreamer-backed cap.

      Raises:
          RuntimeError: If GStreamer cannot instantiate an nvinfer element.
      """
  ```

### Error Handling

- **Raise with enough context to fix the problem without a debugger** —
  the message should say what failed, what value caused it, and where to
  look.

  ```python
  # Bad — traceback already tells you this
  raise RuntimeError("Failed")

  # Bad — tells you what but not why or where to look
  raise RuntimeError(f"Could not create element for '{cap}'")

  # Good — what failed, which value, and how to diagnose
  raise RuntimeError(
      f"Failed to create nvinfer element for capability '{cap}'. "
      "Check that the gst-nvinfer plugin is installed and accessible."
  )
  ```

- **Only catch exceptions you can actually handle** — if you catch it just
  to log and re-raise, that's fine. If you catch it and do nothing, that's
  a bug waiting to happen.

  ```python
  # Bad — swallows the error silently
  try:
      sgie.set_property("config-file-path", path)
  except Exception:
      pass

  # Bad — catches everything including KeyboardInterrupt, MemoryError
  except Exception as e:
      logger.error("Something went wrong: %s", e)

  # Good — catches only what you can handle, with context
  except GLib.Error as e:
      raise RuntimeError(
          f"GStreamer property error on '{cap}': {e.message}"
      ) from e
  ```

- **No empty except blocks** — ever.

### Language Consistency
- **All comments, docstrings, log messages, and string literals must be in
  one language throughout a file.** Default: English. Never mix languages
  mid-comment or mid-function — not even for a single phrase.
- If the user's codebase uses a different language, apply it consistently.
  The rule is consistency, not English specifically.
- Mixed-language comments are a 🔴 REWRITE — translate all non-English
  comments to English and flag this prominently in the summary.

### Large Dict Literals
- **Inline dicts with more than ~5 keys need a builder function** — extract
  into a named function that returns the dict. This makes the shape readable,
  testable, and easy to update.
- The call site becomes: `payload = build_qa_status_payload(cfg, tiler_cols, tiler_rows)`
- Builder function gets a docstring explaining what the dict is used for.

### Magic Numbers
- **Magic numbers need units and context, not just a name** — don't just
  rename `320` to `TRACKER_WIDTH`. Explain the constraint in a comment:
  `TRACKER_INPUT_WIDTH = 320  # minimum width for nvmultiobjecttracker at this model`
- Hardware defaults, port numbers, and resolution constants all need this
  treatment.

### Repeated Conditional Flags
- **If the same flag is checked 3+ times across one function, extract a
  helper** — `if _IS_QA_ENABLED:` scattered through a 100-line function
  means QA setup should live in `_setup_qa_mode(...)`.
- This also applies to `cfg.X` checks repeated throughout — group related
  conditional logic into one place.

### Argument Comments
- **No inline comments explaining what a `None` argument means** —
  `redis_client=_redis_qa,  # None in production, ignored gracefully` means
  the function signature or docstring isn't doing its job. Fix the API
  clarity instead of patching it with a comment.

---

## AI Anti-Pattern Checklist

Run through this mentally on every piece of code before responding:

| Pattern | Example | Fix |
|---|---|---|
| Commenting the obvious | `# increment counter` above `counter += 1` | Delete the comment |
| Generic names | `data`, `result`, `process_data()` | Rename to domain term |
| Banner comments | `# ── Build elements ──` | Extract named function |
| Magic sentinel values | `if interval >= 0` | Named constant or method |
| Unconditional mid-function import | `import sys` inside a function body, no reason | Move to top of file |
| Conditional import with no explanation | `from mjpeg_server import X` inside an `if` block, no comment | Add comment explaining why it's deferred, or extract into a module |
| Aliased import to avoid conflict | `import json as _json` inside a conditional | Move to top, drop alias — the conflict usually doesn't exist |
| Flat procedural blocks | 100-line function doing 6 things | Extract named steps |
| Redundant boilerplate | `if x is not None: return x else: return None` | `return x` |
| Over-defensive try/except | Wrapping everything, catching `Exception` | Catch specific errors only |
| Verbose docstring on trivial function | 10-line NumPy docstring on a 3-line getter | One-line docstring or none |
| Mixed language comments | Spanish comment in English codebase | Translate all to English |
| Large inline dict literal | 25-key dict built inline in a setup function | Extract to builder function |
| Magic numbers without context | `tracker-width: 320` with no explanation | Named constant + comment explaining constraint |
| Repeated flag checks | `if _IS_QA_ENABLED:` 4 times in one function | Extract `_setup_qa_mode()` |
| Argument explanation comments | `redis=client,  # None in prod` | Fix the docstring instead |
| Manual alignment whitespace | `set_property("a",  1)` padded to align | Remove — breaks on edits |
| Async/await mixed with .then() chains | (JS) | Standardize to async/await |

---

## Language-Specific Rules

See the references folder for detailed per-language rules. Load the relevant
file based on the code being reviewed:

- Python → `references/python.md`
- C++ → `references/cpp.md`
- JavaScript / TypeScript → `references/js.md`
- Config files (YAML, TOML, .cfg) → `references/configs.md`

---

## What Humanly Does NOT Do

These are out of scope. If you spot them, flag as a `# NOTE:` comment in
the output and mention in the summary — never silently fix:

- **No performance optimization** — algorithmic changes are a different concern
- **No architecture suggestions** — "you should use a class here" is out of
  scope unless it directly causes a readability problem
- **No bug fixing** — if a bug is spotted, flag it with a `# BUG:` comment and
  note it in the summary, but do not fix it
- **No style debates** — one convention per language, applied consistently

---

## Safety Rules — How Not to Break Code

Structural changes look harmless but can break things in ways that only
surface at runtime. Run through this checklist before every rewrite.

### 1. Check variable scope before extracting functions

Extracting a block into a function silently breaks it if the block reads
variables from the outer scope that you forget to pass as parameters.
Python won't catch this at import time — it fails at runtime.

```python
# Original — block reads `cfg`, `logger`, `SGIE_CONFIGS` from outer scope
sgie_elements = []
for cap in cfg.active_sgies():
    cfg_path = SGIE_CONFIGS.get(cap)
    ...
    logger.info("SGIE loaded: %s", cap)

# Wrong extraction — cfg, logger, SGIE_CONFIGS are missing as parameters
def build_sgie_elements() -> list:  # ← will fail at runtime
    for cap in cfg.active_sgies():  # NameError: cfg is not defined
        ...

# Correct extraction — all dependencies are explicit parameters
def build_sgie_elements(cfg: PipelineConfig) -> list[Gst.Element]:
    for cap in cfg.active_sgies():
        ...
```

**Before extracting any block, list every name it reads that isn't defined
inside the block itself. Each one becomes a parameter.**

### 2. Never move a conditional import to the top without checking why it's there

Moving `from X import Y` out of a conditional block can force an optional
dependency to be installed in all environments — breaking production
deployments that don't have it.

```python
# This import is inside an if-block intentionally:
if _IS_QA_ENABLED:
    from mjpeg_server import MjpegServer  # QA-only dep, not in production

# Moving it to the top silently breaks production:
from mjpeg_server import MjpegServer  # ← ModuleNotFoundError in prod
```

Rule: if an import is inside a conditional, ask why before moving it.
See the Imports rule in Core Rules for the full list of legitimate reasons.

### 3. Never rename a symbol that is part of a public API

Renaming functions, classes, or variables that are imported by other
modules, referenced by name in config files, or used in tests breaks those
callers silently — Python imports don't validate names at import time.

High-risk contexts:
- **Django / Odoo / FastAPI** — view names, model names, URL patterns,
  signal handlers, and celery tasks are often referenced by string
- **ROS 2** — node names, topic names, and parameter names are strings
- **Test files** — `unittest.mock.patch("module.ClassName")` uses the
  string name; renaming the class breaks the patch silently
- **`__all__`** — if a module defines `__all__`, renaming an exported
  name without updating the list breaks external imports

```python
# If another file does this:
from app.routes.cameras import router

# Renaming `router` to `cameras_router` inside cameras.py breaks it:
# ImportError: cannot import name 'router' from 'app.routes.cameras'
```

Before renaming anything, search the codebase for other references to
that name. If you can't search (you only have one file), flag it instead:
```python
# NOTE: renamed from `router` to `cameras_router` — update any imports
# in files that reference this name directly.
```

### 4. Never replace sys.exit() with raise without understanding the caller

`sys.exit(1)` and `raise RuntimeError(...)` behave differently:
- `sys.exit()` terminates the process unconditionally
- `raise` propagates up the call stack — if no caller catches it, it
  also terminates, but callers *can* catch it and continue

In a GStreamer pipeline or a daemon process, the caller may not be
written to handle exceptions. Replacing `sys.exit()` with `raise` is
safer and cleaner *in general*, but flag it in the summary so the
developer can verify their caller handles it.

```python
# Changed sys.exit(1) to raise RuntimeError — verify that the caller
# of this function either catches RuntimeError or is happy to let it
# propagate and terminate the process.
raise RuntimeError(
    f"Failed to create nvinfer element for capability '{cap}'."
)
```

### 5. Never reorder middleware or plugin registration without flagging it

In frameworks like FastAPI, Django, and Express, the order of middleware
registration directly affects execution order. Reordering for aesthetics
(alphabetical, by length) can silently break authentication, CORS, or
rate limiting.

```python
# FastAPI applies middleware in reverse registration order.
# Current execution order: CORS → Audit → RateLimit → handler
# DO NOT reorder these — CORS must run before auth checks.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(CORSMiddleware, ...)
```

Rule: if you touch middleware, signal handler, or plugin registration
order for any reason, always add a comment documenting the execution
order and flag the change in the summary.

### 6. Preserve intentional "ugly" patterns — ask before changing

Some code looks wrong but is deliberate:
- `time.sleep()` in a loop — may be intentional rate limiting
- A deeply nested conditional — may reflect a real decision tree that
  can't be flattened without losing meaning
- A very long function — may be a transaction that must not be split
- `global` variable — may be intentional shared state in a daemon

If something looks like an anti-pattern but has a comment explaining it,
**leave it alone**. If it looks wrong and has no comment, flag it as a
`# NOTE:` but don't change it in rewrite mode.

---

### Safety summary — before submitting any rewrite

Ask yourself:
1. Did I pass all outer-scope variables as explicit parameters to extracted functions?
2. Did I check every moved import for conditional intent?
3. Did I search for (or flag) any renamed public symbols?
4. Did I flag any `sys.exit` → `raise` changes for the developer to verify?
5. Did I preserve middleware/plugin registration order?
6. Did I leave intentional patterns alone or flag them without changing them?

If any answer is "no" or "unsure" — flag it in the summary rather than
silently proceeding.

---

## Output Format

### Review Mode output
```
## Humanly Review

**Mode:** Review
**Language:** Python
**Issues found:** 4 (2 🔴, 1 🟡, 1 🟢)

---

🔴 REWRITE — Lines 3–22 (build_pipeline block)
Why: This flat block handles element creation, configuration, and error
handling for multiple capabilities. It needs a banner comment to explain
itself, which is a signal it should be a named function.
Fix: Extract into `build_sgie_elements(cfg) -> list[Gst.Element]`

🟡 RENAME — Line 9, `cfg_path`
Why: Fine locally, but `sgie_config_path` is clearer when read in isolation.
Fix: Rename to `sgie_config_path`

...

---
**Summary:** Main issue is structural — one flat block doing too much.
Naming is mostly good. No logic changes needed.
```

### Rewrite Mode output
Provide the branch recommendation first, then the full cleaned code, then
the summary:

```
⚠️ Before applying this rewrite, create a branch:
git checkout -b humanly/refactor

[cleaned code here]

---
## What changed
- Extracted `build_sgie_elements()` and `_create_nvinfer_element()` —
  the banner comment is no longer needed
- Added comment on `cfg.sgie_interval >= 0` explaining the sentinel value —
  NOTE left suggesting sgie_interval_is_enabled() for a future refactor
- Replaced `sys.exit(1)` with `RuntimeError` — flag: verify your caller
  handles this or is happy to let it terminate the process
- Removed comment on line 7 — it described what the code does, not why

⚠️ No logic was changed. All behavior is preserved.
```

If the rewrite includes high-risk changes, upgrade the opening warning:
```
⚠️ This rewrite includes structural changes that carry runtime risk
(function extraction, error handling change). Strongly recommend a
branch and running your test suite before merging:

git checkout -b humanly/refactor
# apply changes
python -m pytest
```

---

## Examples

**Read these before rewriting.** The examples directory contains real
before/after pairs from production code. Use them to calibrate what
"messy" looks like in each domain and what the target quality looks like.
They are references, not templates — don't copy structure blindly.

Available examples:

| File | Domain | Key issues illustrated |
|---|---|---|
| `examples/before/deepstream_sgie.py` | GStreamer / DeepStream | Banner comment, magic sentinel, `sys.exit`, flat block |
| `examples/after/deepstream_sgie.py` | GStreamer / DeepStream | Extracted functions, named constant, `RuntimeError` |
| `examples/before/pipeline_setup.py` | GStreamer / DeepStream | Mixed Spanish/English, mid-function imports, repeated flag checks, large inline dict, magic numbers |
| `examples/after/pipeline_setup.py` | GStreamer / DeepStream | Conservative extraction, English-only, deferred imports explained, builder function |
| `examples/before/fastapi_main.py` | FastAPI entrypoint | Good structure, missing comments on non-obvious decisions |
| `examples/after/fastapi_main.py` | FastAPI entrypoint | Module docstring, middleware order explained, deferred imports documented, gotchas flagged |

When the user's code matches a domain in the table, read both the before
and after for that domain before starting your review or rewrite.
