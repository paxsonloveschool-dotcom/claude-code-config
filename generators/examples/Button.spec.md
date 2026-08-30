# Button Component Specification

## Purpose
A reusable, accessible button component for forms and interactive UI.

## Features

### Variants
- `primary` — Main action, prominent styling
- `secondary` — Alternative action
- `danger` — Destructive action (delete, cancel, etc.)
- `ghost` — Minimal styling, text only

### States
- **Normal** — Default, interactive state
- **Disabled** — Non-interactive, greyed out
- **Loading** — Shows spinner, prevents clicks
- **Active** — Highlighted/selected state

### Sizes
- `sm` — Small button for compact UI
- `md` — Default/medium size
- `lg` — Large button for primary actions

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | string | 'primary' | Button style variant |
| size | string | 'md' | Button size |
| disabled | boolean | false | Disable interaction |
| loading | boolean | false | Show loading spinner |
| icon | ReactNode | - | Icon to display (left side) |
| rightIcon | ReactNode | - | Icon on right side |
| onClick | function | - | Click handler |
| children | ReactNode | - | Button text/content |
| className | string | - | CSS class (for styling) |
| type | string | 'button' | HTML button type |
| ariaLabel | string | - | Accessibility label |

### Accessibility
- ARIA labels for screen readers
- Keyboard support (Enter, Space)
- Focus management
- Loading state announcements

### Edge Cases
- Handle null/undefined children
- Prevent double-click submissions (debounce if needed)
- Support custom content beyond text
- Work with and without icons
- Proper disabled state handling

## Example Usage

```jsx
// Basic button
<Button>Click me</Button>

// With variant and size
<Button variant="danger" size="lg">Delete</Button>

// With loading state
<Button loading disabled>Processing...</Button>

// With icon
<Button icon={<ChevronRight />}>Next</Button>

// As form button
<Button type="submit">Submit Form</Button>
```

## Testing Requirements

Tests should cover:
1. All variant combinations
2. All size combinations
3. Disabled state prevents clicks
4. Loading state shows spinner
5. Icon rendering (with and without)
6. Children rendering
7. Click handlers fire correctly
8. ARIA attributes present
9. Keyboard interactions
10. Focus management
