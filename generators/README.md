# React Component Generator

An AI-powered code generator that writes React components using Claude, validates them with tests, and automatically fixes failures through iterative prompting.

## How It Works

The generator implements a self-prompting loop:

1. **Specification** → Read your component requirements
2. **Generation** → Call Claude API with the spec
3. **Validation** → Run Jest tests on generated code
4. **Error Feedback** → If tests fail, extract error message
5. **Regeneration** → Send error + spec back to Claude
6. **Retry** → Loop until tests pass (max 3 attempts)
7. **Commit** → Save working component to git

## Architecture

- `generate.js` — Example-driven generator (Button component)
- `generate-interactive.js` — Interactive CLI for custom components
- `jest.config.js` — Jest test configuration
- `setup.js` — Jest environment setup
- `generated/` — Output directory for generated components

## Setup

```bash
cd generators
npm install
export ANTHROPIC_API_KEY="your-api-key"
```

## Usage

### Automatic Example (Button Component)

```bash
npm run generate
```

This generates a Button component with:
- Multiple variants (primary, secondary, danger)
- Disabled & loading states
- Icon support
- Size variants
- Full test coverage

### Interactive CLI

```bash
node generate-interactive.js
```

Then answer prompts:
```
Component name: Card
Brief description: A reusable card component for displaying content
Key features: header, footer, icon support, clickable variant
Max retry attempts: 5
```

The generator will:
1. Prompt Claude to write the component
2. Run tests
3. If tests fail, automatically retry with the error message
4. Loop until tests pass
5. Commit the working component

## Output

Generated components are saved to:
```
generated/
├── ComponentName/
│   ├── ComponentName.jsx      # The component
│   └── ComponentName.test.jsx  # Full test suite
```

## Example: Button Component Generation

**Specification:**
```
A reusable Button component with:
- Support for different variants (primary, secondary, danger)
- Disabled state
- Loading state with spinner
- Icon support (left and right)
- Size variants (sm, md, lg)
- Click handler
- Accessible (ARIA labels, keyboard support)
```

**What Claude generates:**

```jsx
// Button.jsx
export default function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon,
  children,
  onClick,
  ...props
}) {
  // Full implementation with all variants
}
```

```jsx
// Button.test.jsx
describe('Button', () => {
  test('renders with primary variant', () => { ... });
  test('handles disabled state', () => { ... });
  test('shows loading spinner', () => { ... });
  // All test cases passing
});
```

## How Self-Prompting Works

When tests fail, the generator:

1. **Extracts the error:**
   ```
   ● Button › renders with icon
   Error: expect(element).toBeInTheDocument()
   ```

2. **Builds a new prompt with context:**
   ```
   Generate a React component based on this specification:
   [original spec]

   Previous test failure to fix:
   [extracted error message]

   Analyze the error and fix the issue.
   ```

3. **Claude fixes and regenerates** with the feedback loop in mind

4. **Tests run again** → Success or loop continues

## API Integration

The generator uses the Anthropic SDK:

```javascript
const message = await client.messages.create({
  model: "claude-opus-4-1-20250805",
  max_tokens: 2048,
  messages: [{
    role: "user",
    content: prompt,
  }],
});
```

## Configuration

Edit `generate-interactive.js` or `generate.js` to:
- Change the model (`claude-opus-4-1-20250805`)
- Adjust max retries (default: 3)
- Modify prompt templates
- Customize component output location

## Testing Framework

Uses Jest + React Testing Library:
- DOM rendering tests
- User interaction tests
- Edge case validation
- Component prop validation

## What Gets Committed

After successful generation:
```bash
git add generated/
git commit -m "feat: generate ComponentName component with tests (YYYY-MM-DD)"
```

Only successfully tested components are committed.

## Limitations

- Requires ANTHROPIC_API_KEY environment variable
- Max tokens per generation: 2048 (adjustable)
- Complex components may need manual refinement
- Tests must pass within max retry attempts

## Future Enhancements

- Batch component generation
- Custom test templates
- Storybook integration
- TypeScript generation
- Component library scaffolding
- Custom hooks generation

## License

Same as claude-code-config repo
