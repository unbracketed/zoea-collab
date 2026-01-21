import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// vi.mock is hoisted, so all mock implementations must be inline

// Mock YooptaEditor to verify props are passed correctly
vi.mock('./YooptaEditor', () => ({
  __esModule: true,
  default: vi.fn(({ value, readOnly, className }) => (
    <div
      data-testid="yoopta-editor"
      data-readonly={readOnly}
      data-classname={className}
    >
      {value && typeof value === 'object' && JSON.stringify(value)}
      {value && typeof value === 'string' && value}
    </div>
  )),
}));

import YooptaViewer from './YooptaViewer';
import YooptaEditorMock from './YooptaEditor';

describe('YooptaViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "No content available" when value is null', () => {
    render(<YooptaViewer value={null} />);

    expect(screen.getByText('No content available.')).toBeInTheDocument();
    expect(screen.queryByTestId('yoopta-editor')).not.toBeInTheDocument();
  });

  it('renders "No content available" when value is undefined', () => {
    render(<YooptaViewer />);

    expect(screen.getByText('No content available.')).toBeInTheDocument();
    expect(screen.queryByTestId('yoopta-editor')).not.toBeInTheDocument();
  });

  it('renders "No content available" when value is empty string', () => {
    render(<YooptaViewer value="" />);

    expect(screen.getByText('No content available.')).toBeInTheDocument();
    expect(screen.queryByTestId('yoopta-editor')).not.toBeInTheDocument();
  });

  it('renders YooptaEditor with value when provided', () => {
    const testValue = {
      'block-1': {
        id: 'block-1',
        type: 'Paragraph',
        value: [{ children: [{ text: 'Test content' }] }],
      },
    };

    render(<YooptaViewer value={testValue} />);

    expect(screen.queryByText('No content available.')).not.toBeInTheDocument();
    expect(screen.getByTestId('yoopta-editor')).toBeInTheDocument();
    expect(screen.getByTestId('yoopta-editor')).toHaveTextContent('Test content');
  });

  it('passes readOnly=true to YooptaEditor', () => {
    const testValue = { block: { type: 'Paragraph' } };

    render(<YooptaViewer value={testValue} />);

    const editor = screen.getByTestId('yoopta-editor');
    expect(editor).toHaveAttribute('data-readonly', 'true');
  });

  it('passes className to YooptaEditor', () => {
    const testValue = { block: { type: 'Paragraph' } };

    render(<YooptaViewer value={testValue} className="custom-viewer-class" />);

    const editor = screen.getByTestId('yoopta-editor');
    expect(editor).toHaveAttribute('data-classname', 'custom-viewer-class');
  });

  it('renders with JSON string value', () => {
    const testValue = JSON.stringify({
      'block-1': {
        id: 'block-1',
        type: 'Paragraph',
        value: [{ children: [{ text: 'JSON content' }] }],
      },
    });

    render(<YooptaViewer value={testValue} />);

    expect(screen.getByTestId('yoopta-editor')).toBeInTheDocument();
    expect(screen.getByTestId('yoopta-editor')).toHaveTextContent('JSON content');
  });

  it('applies text-text-secondary class to empty state', () => {
    const { container } = render(<YooptaViewer value={null} />);

    const emptyMessage = container.querySelector('.text-text-secondary');
    expect(emptyMessage).toBeInTheDocument();
    expect(emptyMessage).toHaveTextContent('No content available.');
  });

  it('applies custom className to empty state', () => {
    const { container } = render(<YooptaViewer value={null} className="my-custom-class" />);

    const emptyMessage = container.querySelector('.my-custom-class');
    expect(emptyMessage).toBeInTheDocument();
  });

  it('calls YooptaEditor with correct props', () => {
    const testValue = { test: true };

    render(<YooptaViewer value={testValue} className="test-class" />);

    expect(YooptaEditorMock).toHaveBeenCalled();
    const callArgs = YooptaEditorMock.mock.calls[0][0];
    expect(callArgs.value).toEqual(testValue);
    expect(callArgs.readOnly).toBe(true);
    expect(callArgs.className).toBe('test-class');
  });
});
