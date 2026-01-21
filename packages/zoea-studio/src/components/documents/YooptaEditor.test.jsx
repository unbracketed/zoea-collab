import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock window.matchMedia before tests run
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// vi.mock is hoisted, so we cannot use variables defined below. Use inline implementations.

// Mock @yoopta/editor
vi.mock('@yoopta/editor', () => ({
  __esModule: true,
  default: ({ value, onChange, readOnly, placeholder }) => (
    <div
      data-testid="yoopta-editor-core"
      data-readonly={readOnly}
      data-placeholder={placeholder}
    >
      {value && JSON.stringify(value)}
    </div>
  ),
  createYooptaEditor: () => ({
    focus: vi.fn(),
    blur: vi.fn(),
  }),
}));

// Mock @yoopta/action-menu-list
vi.mock('@yoopta/action-menu-list', () => ({
  __esModule: true,
  default: vi.fn(),
  DefaultActionMenuRender: vi.fn(),
}));

// Mock @yoopta/toolbar
vi.mock('@yoopta/toolbar', () => ({
  __esModule: true,
  default: vi.fn(),
  DefaultToolbarRender: vi.fn(),
}));

// Mock yoopta plugins config
vi.mock('../../config/yooptaPlugins', () => ({
  plugins: [{ type: 'Paragraph' }, { type: 'HeadingOne' }, { type: 'Image' }],
  MARKS: ['bold', 'italic'],
}));

// Mock yoopta image plugin
vi.mock('../../config/yooptaImagePlugin', () => ({
  createProjectImagePlugin: vi.fn(() => ({ type: 'Image', custom: true })),
  insertImageFromLibrary: vi.fn(),
}));

// Mock theme store - uses module variable for test control
vi.mock('../../stores/themeStore', async () => {
  // Use a getter so tests can modify it
  let mode = 'light';
  return {
    useThemeStore: (selector) => selector({ mode }),
    __setMode: (newMode) => { mode = newMode; },
  };
});

// Mock ImagePickerModal
vi.mock('./ImagePickerModal', () => ({
  __esModule: true,
  default: ({ isOpen, onClose, onSelect }) =>
    isOpen ? (
      <div data-testid="image-picker-modal">
        <button data-testid="close-picker" onClick={onClose}>
          Close
        </button>
        <button
          data-testid="select-image"
          onClick={() =>
            onSelect({
              src: 'https://example.com/image.png',
              alt: 'Test Image',
              width: 800,
              height: 600,
            })
          }
        >
          Select
        </button>
      </div>
    ) : null,
}));

import YooptaEditor from './YooptaEditor';
import { createProjectImagePlugin } from '../../config/yooptaImagePlugin';

describe('YooptaEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders without crashing', () => {
    render(<YooptaEditor />);
    expect(screen.getByTestId('yoopta-editor-core')).toBeInTheDocument();
  });

  it('renders with initial value', () => {
    const testValue = {
      'block-1': {
        id: 'block-1',
        type: 'Paragraph',
        value: [{ children: [{ text: 'Hello World' }] }],
      },
    };

    render(<YooptaEditor value={testValue} />);

    const editor = screen.getByTestId('yoopta-editor-core');
    expect(editor).toHaveTextContent('Hello World');
  });

  it('parses JSON string value', () => {
    const testValue = JSON.stringify({
      'block-1': {
        id: 'block-1',
        type: 'Paragraph',
        value: [{ children: [{ text: 'From JSON' }] }],
      },
    });

    render(<YooptaEditor value={testValue} />);

    const editor = screen.getByTestId('yoopta-editor-core');
    expect(editor).toHaveTextContent('From JSON');
  });

  it('treats empty object as undefined', () => {
    render(<YooptaEditor value={{}} />);

    const editor = screen.getByTestId('yoopta-editor-core');
    // Empty object should be treated as undefined, so no content
    expect(editor).not.toHaveTextContent('{}');
  });

  it('renders in read-only mode', () => {
    render(<YooptaEditor readOnly={true} />);

    const editor = screen.getByTestId('yoopta-editor-core');
    expect(editor).toHaveAttribute('data-readonly', 'true');
  });

  it('renders with custom placeholder', () => {
    render(<YooptaEditor placeholder="Type something..." />);

    const editor = screen.getByTestId('yoopta-editor-core');
    expect(editor).toHaveAttribute('data-placeholder', 'Type something...');
  });

  it('shows image library button when projectId and workspaceId provided', () => {
    render(<YooptaEditor projectId={1} workspaceId={2} />);

    expect(screen.getByRole('button', { name: /insert from library/i })).toBeInTheDocument();
  });

  it('hides image library button in read-only mode', () => {
    render(<YooptaEditor projectId={1} workspaceId={2} readOnly={true} />);

    expect(screen.queryByRole('button', { name: /insert from library/i })).not.toBeInTheDocument();
  });

  it('hides image library button without projectId', () => {
    render(<YooptaEditor workspaceId={2} />);

    expect(screen.queryByRole('button', { name: /insert from library/i })).not.toBeInTheDocument();
  });

  it('opens image picker modal on button click', () => {
    render(<YooptaEditor projectId={1} workspaceId={2} />);

    // Modal should not be visible initially
    expect(screen.queryByTestId('image-picker-modal')).not.toBeInTheDocument();

    // Click the button
    fireEvent.click(screen.getByRole('button', { name: /insert from library/i }));

    // Modal should now be visible
    expect(screen.getByTestId('image-picker-modal')).toBeInTheDocument();
  });

  it('closes image picker modal on close', () => {
    render(<YooptaEditor projectId={1} workspaceId={2} />);

    // Open modal
    fireEvent.click(screen.getByRole('button', { name: /insert from library/i }));
    expect(screen.getByTestId('image-picker-modal')).toBeInTheDocument();

    // Close modal
    fireEvent.click(screen.getByTestId('close-picker'));
    expect(screen.queryByTestId('image-picker-modal')).not.toBeInTheDocument();
  });

  it('creates project image plugin with correct params', () => {
    render(<YooptaEditor projectId={1} workspaceId={2} />);

    expect(createProjectImagePlugin).toHaveBeenCalledWith({
      projectId: 1,
      workspaceId: 2,
    });
  });

  it('applies custom className', () => {
    const { container } = render(<YooptaEditor className="custom-class" />);

    const wrapper = container.querySelector('.yoopta-editor-container');
    expect(wrapper).toHaveClass('custom-class');
  });

  it('applies yoopta-editor-container class', () => {
    const { container } = render(<YooptaEditor />);

    const wrapper = container.querySelector('.yoopta-editor-container');
    expect(wrapper).toBeInTheDocument();
  });
});
