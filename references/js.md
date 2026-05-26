# JavaScript / TypeScript — Humanly Reference

## Imports
- All imports at the top of the file
- Order: Node built-ins → third-party → local
- Named imports over default where possible for clarity
- No `require()` in TypeScript — use `import`

## Naming
- `camelCase` for variables, functions, methods
- `PascalCase` for classes, interfaces, types, enums
- `UPPER_SNAKE_CASE` for true constants
- `_` prefix for intentionally unused parameters: `(_event) =>`
- Boolean variables/functions should read as questions: `isLoading`, `hasError`, `canRetry`

## TypeScript Specifics
- Explicit return types on exported functions
- Avoid `any` — use `unknown` and narrow, or define the type
- Prefer `interface` for object shapes, `type` for unions/intersections
- Use `readonly` on properties that shouldn't be mutated
- Enums for fixed sets of values over string literals (or `as const` objects)

## Async
- `async/await` consistently — never mix with `.then()` chains
- Always `await` Promises — unhandled floating promises are silent bugs
- Use `Promise.all()` for concurrent independent async operations
- Label async functions clearly: `fetchUserData()`, not `getData()`

## Error Handling
- `try/catch` only around code that can actually throw
- Always type the caught error: `catch (err) { if (err instanceof Error) ... }`
- Never empty catch blocks
- Propagate errors with context: `throw new Error(\`Failed to load config: \${err.message}\`)`

## React (if applicable)
- One component per file
- Props interface named `[ComponentName]Props`
- Extract complex logic into named custom hooks (`useX`)
- No inline object/function creation in JSX props (causes re-renders)

## Patterns to prefer
- `const` by default, `let` only when reassignment is needed, never `var`
- Optional chaining: `user?.profile?.name` over nested null checks
- Nullish coalescing: `value ?? defaultValue` over `value || defaultValue`
- Destructuring for clarity: `const { name, age } = user`
- Template literals over string concatenation

## Patterns to avoid
- `==` — always use `===`
- `arguments` object — use rest params `...args`
- Callback hell — flatten with async/await
- Magic strings inline — named constants or enums
- `console.log` left in production code — use a logger
