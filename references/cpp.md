# C++ — Humanly Reference

## File Structure
- Headers: `.hpp`, Implementation: `.cpp`
- Header guards: `#pragma once` (preferred over `#ifndef` guards)
- Include order: paired header → stdlib → third-party → project local
- No implementation in headers except templates and `inline` functions

## Naming
- `PascalCase` for classes and structs
- `snake_case` for functions, variables, members
- `UPPER_SNAKE_CASE` for constants and macros
- `m_` prefix for private member variables: `m_config`, `m_elements`
- Avoid cryptic abbreviations: `pipeline_config` over `plcfg`

## Comments
- Use `//` for inline; `/* */` only for block-level file/class headers
- Document *why* non-obvious memory ownership decisions were made
- Mark `// TODO:`, `// FIXME:`, `// BUG:` explicitly

## RAII and Resource Management
- Prefer smart pointers: `std::unique_ptr`, `std::shared_ptr` over raw `new`/`delete`
- Destructors should release all owned resources
- Document ownership clearly when passing raw pointers

## Modern C++ Preferences (C++17+)
- `auto` where type is obvious from context; explicit type where it aids reading
- Range-based for loops over index loops where index isn't needed
- `nullptr` over `NULL` or `0`
- `std::optional<T>` over sentinel values like `-1` or `nullptr` for "no value"
- Structured bindings: `auto [key, val] = pair;`
- `[[nodiscard]]` on functions whose return value must not be ignored

## Error Handling
- Prefer exceptions for truly exceptional cases
- Return `std::optional` or a result type for expected failure modes
- Document exception guarantees (noexcept, strong, basic)
- Never swallow exceptions silently

## Patterns to avoid
- `using namespace std;` in headers (pollutes consumer namespaces)
- Raw arrays — use `std::array` or `std::vector`
- C-style casts — use `static_cast`, `reinterpret_cast` explicitly
- Magic numbers inline — named `constexpr` constants instead
