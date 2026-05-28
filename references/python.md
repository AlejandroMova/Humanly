# Python — Humanly Reference

## Imports
- Order: stdlib → third-party → local, one blank line between groups
- No `import *`
- No imports inside functions or conditionals (except TYPE_CHECKING guards)
- Prefer explicit: `from pathlib import Path` over `import pathlib`

## Naming
- `snake_case` for variables, functions, modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- `_single_leading_underscore` for private helpers
- `__dunder__` only for Python special methods
- Avoid: `l`, `O`, `I` as single-letter names (visually ambiguous)

## Type Hints
- Add type hints to all function signatures in non-trivial code
- Use `list[X]`, `dict[K, V]`, `tuple[X, ...]` (Python 3.9+) over `List`, `Dict`
- Use `X | None` over `Optional[X]` (Python 3.10+)
- Use `-> None` explicitly on functions with only side effects

## Docstrings
- One-line docstring for simple utilities: `"""Return the config path for cap."""`
- Google-style for anything with params/returns:
  ```python
  def build_sgie_elements(cfg: PipelineConfig) -> list[Gst.Element]:
      """Instantiate one nvinfer SGIE element per active capability.

      Capabilities backed by Python workers are skipped — they don't
      use a GStreamer inference element.

      Args:
          cfg: Pipeline configuration used to determine which capabilities
              need a GStreamer inference element (via cfg.active_sgies())
              and to set the inference interval. Negative sgie_interval
              means the interval is disabled and left at its default.

      Returns:
          One configured nvinfer Gst.Element per GStreamer-backed capability,
          in iteration order. Empty list if all active capabilities are
          handled by Python workers.

      Raises:
          RuntimeError: If an nvinfer element cannot be created — check
              that the gst-nvinfer plugin is installed and accessible.
      """
  ```
- **Args:** document what the parameter is *for*, not just its type.
  The type hint already says the type — the docstring adds:
  - What the function actually uses it for (which fields, which method calls)
  - Constraints or valid ranges when non-obvious (`negative means disabled`)
  - What `None` means if the parameter is nullable
- **Returns:** document what the returned value *represents*, not just its type.
  Include edge cases: when can it be empty, `None`, or zero-length?
  If order or structure is guaranteed, say so.
- **Raises:** document the condition that triggers the exception, not just its
  type: `RuntimeError: If GStreamer cannot create the element — check plugin install.`
- No docstring needed on `__init__` if the class docstring covers it
- Module-level docstring: one paragraph explaining purpose + usage example

## Error Handling
- Raise specific exceptions: `ValueError`, `RuntimeError`, `FileNotFoundError`
- Include context in messages: `raise RuntimeError(f"Failed to create '{name}'")`
- Never: `except Exception: pass`
- Use `logging.exception()` inside except blocks to preserve tracebacks

## Patterns to prefer
- Early returns over nested if/else
- `pathlib.Path` over `os.path` string manipulation
- Context managers (`with`) for any resource that needs cleanup
- `dataclasses` or `pydantic` over raw dicts for structured config
- `enumerate()` over `range(len(x))`
- `f-strings` over `.format()` or `%` formatting

## Patterns to avoid
- Mutable default arguments: `def f(x=[])` → use `def f(x=None): if x is None: x = []`
- Bare `except:` (catches KeyboardInterrupt too)
- `global` variables
- Long lambda chains — extract into named functions
- `print()` in library/module code — use `logging`
