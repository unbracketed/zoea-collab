# Frontend Testing Guide

## Overview

This project uses Vitest as the testing framework along with React Testing Library for component testing.

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with UI
npm test:ui

# Generate coverage report
npm test:coverage
```

## Test Structure

- `src/test/setup.js` - Test environment setup, including localStorage mock
- `src/**/*.test.{js,jsx}` - Test files colocated with source code

## Existing Test Coverage

### ConversationContext (11 tests)
- ✅ Hook validation outside provider
- ✅ Loading conversations on mount
- ✅ Error handling for API failures
- ✅ Selecting conversations and loading messages
- ✅ Persisting conversation ID to localStorage
- ✅ Clearing state for new conversations
- ✅ Creating new conversations
- ✅ Adding messages
- ✅ localStorage persistence and recovery

### API Service (8 tests)
- ✅ Fetching conversations
- ✅ Fetching specific conversations with messages
- ✅ Sending messages
- ✅ Including conversation_id when provided
- ✅ Omitting conversation_id when null
- ✅ Authentication status checks
- ✅ 401 error handling

## Writing New Tests

### Context/Hook Testing
```javascript
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('MyContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should do something', async () => {
    const { result } = renderHook(() => useMyContext(), {
      wrapper: MyProvider,
    });

    await waitFor(() => {
      expect(result.current.someValue).toBe(expected);
    });
  });
});
```

### Component Testing
```javascript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent prop="value" />);

    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

### API Testing
```javascript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('API Service', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('should call API correctly', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: 'value' }),
    });

    const result = await api.someMethod();

    expect(result).toEqual({ data: 'value' });
  });
});
```

## Important Fixes Implemented

### 1. Race Condition Protection
The `selectConversation` function now includes race condition protection using a ref-based call ID system. This prevents state corruption when rapidly switching between conversations.

### 2. Memoized Context Functions
All ConversationContext functions are wrapped in `useCallback` to prevent unnecessary re-renders and ensure stable function references across renders.

### 3. localStorage Error Handling
While basic error handling exists (console.error), tests verify that the system degrades gracefully when localStorage is unavailable.

## Next Steps for Improved Coverage

1. **Component Tests**: Add tests for ChatPage, ConversationList, ConversationHeader
2. **Integration Tests**: Test the full conversation creation and selection flow
3. **Error Boundary Tests**: Verify error boundary behavior
4. **Accessibility Tests**: Use jest-axe for automated a11y testing
5. **Visual Regression**: Consider adding visual regression testing with Storybook

## Notes

- The `act()` warnings in test output are expected and don't affect test results
- Console errors in tests (e.g., "Failed to load conversations") are expected for error handling tests
- All 19 tests currently pass successfully
