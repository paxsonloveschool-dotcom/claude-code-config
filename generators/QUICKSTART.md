# Quick Start Guide

## 1. Setup

```bash
cd generators
npm install
export ANTHROPIC_API_KEY="your-key-here"
```

## 2. Run Example Generator

```bash
npm run generate
```

This generates a Button component with automatic test validation and git commit.

## 3. Generate Custom Components

### Option A: Interactive CLI
```bash
node generate-interactive.js
```

Follow the prompts to describe your component.

### Option B: From Spec File
```bash
node examples/generate-from-spec.js examples/Button.spec.md MyComponent
```

## 4. Generated Output

Components are saved to `generated/<ComponentName>/`:
```
generated/Button/
├── Button.jsx          # Your component
└── Button.test.jsx     # Full test suite
```

## 5. How It Works

The generator creates a self-prompting loop:

1. **Read spec** → Parse your requirements
2. **Prompt Claude** → "Write a Button component with variants..."
3. **Run tests** → Execute Jest on the generated code
4. **Test fail?** → Extract error message
5. **Reprompt** → Send error + spec back to Claude
6. **Retry** → Loop up to 3 times
7. **Success** → Commit working component to git

## 6. Example Flow

```
User: "Generate a Card component with header and footer"
    ↓
Claude: "Here's a Card component..."
    ↓
Jest: "❌ Test failed: TypeError: Cannot read property 'children'"
    ↓
Claude: "Got it, let me fix the children handling..."
    ↓
Jest: "✅ All tests passed!"
    ↓
Git: Commit: "feat: generate Card component with tests"
```

## 7. Customization

### Change Model
Edit `generate.js` line with `model: "claude-opus-4-1-20250805"`

### Adjust Retry Attempts
Change `maxRetries = 3` to your preferred number

### Modify Test Output
Edit `buildPrompt()` to customize test requirements

## 8. Troubleshooting

**"No ANTHROPIC_API_KEY"**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**"Tests still failing after retries"**
- Review the generated component in `generated/ComponentName/`
- Check test output for specific error messages
- Manually fix and increase maxRetries if needed

**"Git commit failed"**
- Run `git status` to see any issues
- Ensure you're in the repo root
- Check git configuration

## 9. Next Steps

- ✅ Generate multiple components
- ✅ Build a full component library
- ✅ Create custom spec templates
- ✅ Extend test requirements
- ✅ Add Storybook integration
