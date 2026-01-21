# React StrictMode: Patterns and Pitfalls

## Overview

This document captures critical lessons learned from debugging an infinite loop bug caused by improper handling of React's StrictMode behavior. **Required reading before implementing data loading in new components.**

## The Problem

### What Happened
- Infinite loop of API requests after user login
- Hundreds of `/api/auth/check` and `/api/conversations` requests per second
- App completely unusable
- Users saw only loading spinners, never reached the dashboard

### Root Causes
1. **React StrictMode** intentionally mounts → unmounts → remounts components in development
2. **useRef for deduplication** doesn't survive the unmount/remount cycle
3. **Duplicate AuthGuard** wrapping at two levels (main.jsx AND Routes.jsx)
4. **Result**: Every remount triggered new API calls

## Understanding React StrictMode

React StrictMode is **enabled by default** in development and:
- Mounts components
- Unmounts them immediately
- Remounts them again
- This helps detect side effects and prepare for React's future concurrent features

**Critical insight**: `useRef` gets reset on every mount. The unmount/remount cycle creates a **fresh component instance** with **fresh refs**.

## The Anti-Pattern ❌

**DO NOT DO THIS:**

```javascript
// ❌ WRONG - Component-level deduplication with useRef
function MainLayout() {
  const loadConversations = useConversationStore((state) => state.loadConversations);
  const hasLoadedConversations = useRef(false);

  useEffect(() => {
    if (!hasLoadedConversations.current) {
      hasLoadedConversations.current = true;
      loadConversations(); // Will run TWICE in StrictMode!
    }
  }, []);

  // ...
}
```

**Why this fails:**
1. First mount: `hasLoadedConversations.current = false` → calls `loadConversations()`
2. StrictMode unmounts component → ref is destroyed
3. StrictMode remounts component → **NEW ref** with `current = false` again
4. Second mount: `hasLoadedConversations.current = false` → calls `loadConversations()` AGAIN
5. Result: Duplicate API calls, infinite loops, disaster

## The Correct Pattern ✅

**Store-level deduplication survives remounts:**

```javascript
// ✅ CORRECT - Zustand store with deduplication flag
export const useConversationStore = create((set, get) => ({
  conversations: [],
  hasLoadedConversations: false, // ← Store state persists!

  loadConversations: async () => {
    // Check flag INSIDE the action
    if (get().hasLoadedConversations) {
      return; // Already loaded, skip
    }

    try {
      set({ hasLoadedConversations: true });
      const data = await api.fetchConversations();
      set({ conversations: data.conversations || [] });
    } catch (err) {
      console.error('Failed to load:', err);
      set({ hasLoadedConversations: false }); // Reset on error
    }
  },
}));

// Component just calls the action - store handles deduplication
function MainLayout() {
  const loadConversations = useConversationStore((state) => state.loadConversations);

  useEffect(() => {
    loadConversations(); // ✅ Store prevents duplicates
  }, [loadConversations]);

  // ...
}
```

**Why this works:**
1. First mount: Store checks `hasLoadedConversations = false` → loads data, sets flag to `true`
2. StrictMode unmounts component → **Store state remains intact**
3. StrictMode remounts component → Calls `loadConversations()` again
4. Store checks `hasLoadedConversations = true` → Returns early, no duplicate request
5. Result: Only ONE API call, perfect behavior

## Additional Issues Found

### Duplicate Route Guards
We had AuthGuard in TWO places:

```javascript
// main.jsx - ❌ WRONG
<StrictMode>
  <BrowserRouter>
    <AuthGuard>  {/* ← First guard */}
      <App />
    </AuthGuard>
  </BrowserRouter>
</StrictMode>

// Routes.jsx
<Route element={
  <AuthGuard>  {/* ← Second guard! */}
    <MainLayout />
  </AuthGuard>
}>
```

**Fix**: Keep guards in ONE place (Routes.jsx), remove from main.jsx.

## Best Practices

### 1. Always Test with StrictMode Enabled
- StrictMode is the default in development - keep it that way
- Don't disable it to "fix" bugs - fix the bugs properly instead
- Production builds don't have StrictMode, but you want to catch issues in dev

### 2. Use Store State for "One-Time" Flags
- ✅ `hasLoadedData` in Zustand store
- ✅ `isInitialized` in Zustand store
- ❌ `hasLoaded.current` in component useRef

### 3. Put Deduplication Logic in Store Actions
```javascript
// ✅ Deduplication in the action
loadData: async () => {
  if (get().hasLoadedData) return;
  set({ hasLoadedData: true });
  // ... fetch and store data
}

// Component just calls it
useEffect(() => {
  loadData();
}, [loadData]);
```

### 4. Single Source of Truth for Guards
- Route protection in Routes.jsx ONLY
- Don't wrap guards at multiple levels
- Each guard adds another mount/unmount cycle

### 5. Reset Flags on Error
```javascript
try {
  set({ hasLoadedData: true });
  const data = await api.fetchData();
  set({ data });
} catch (err) {
  set({ hasLoadedData: false }); // ← Allow retry on error
  throw err;
}
```

## Debugging Checklist

If you see infinite loops or duplicate API calls:

1. **Check for useRef deduplication** - replace with store state
2. **Verify store actions check flags** - `if (get().hasLoaded) return;`
3. **Look for duplicate guards/providers** - should only be ONE level deep
4. **Confirm StrictMode is enabled** - `<StrictMode>` in main.jsx
5. **Check browser Network tab** - look for repeated identical requests
6. **Add console.logs in useEffect** - you'll see them run twice in StrictMode

## Real-World Example

Our actual fix (commit cc7bdda):

**Before** (infinite loop):
```javascript
// MainLayout.jsx - ❌ BROKEN
const hasLoadedConversations = useRef(false);
useEffect(() => {
  if (!hasLoadedConversations.current) {
    hasLoadedConversations.current = true;
    loadConversations(); // Runs twice!
  }
}, []);
```

**After** (works perfectly):
```javascript
// conversationStore.js - ✅ FIXED
export const useConversationStore = create((set, get) => ({
  hasLoadedConversations: false,

  loadConversations: async () => {
    if (get().hasLoadedConversations) return; // Early return
    set({ hasLoadedConversations: true });
    const data = await api.fetchConversations();
    set({ conversations: data.conversations || [] });
  },
}));

// MainLayout.jsx - ✅ FIXED
useEffect(() => {
  loadConversations(); // Store handles everything
}, [loadConversations]);
```

## When to Use Each Approach

### Use Store State (`hasLoadedX`) When:
- ✅ Loading initial data on app/component mount
- ✅ One-time initialization that should survive remounts
- ✅ State that should persist across component lifecycle
- ✅ **Anything that makes API calls or has side effects**

### Use useRef When:
- ✅ Storing DOM element references
- ✅ Storing mutable values that don't trigger re-renders
- ✅ Storing timers/intervals
- ❌ **NOT for preventing duplicate effects in StrictMode**

## Summary

**The Golden Rule**: If you're using `useRef` to prevent duplicate API calls or duplicate effects, **you're doing it wrong**. Move the deduplication flag to your Zustand store.

React StrictMode is your friend - it catches bugs before production. Don't fight it, work with it by using store state for persistence across mount cycles.

## References

- Commit `b2faba0`: Initial useRef approach (had bugs)
- Commit `cc7bdda`: Store-based fix (works correctly)
- Files modified:
  - `frontend/src/stores/conversationStore.js`
  - `frontend/src/components/MainLayout.jsx`
  - `frontend/src/main.jsx`
