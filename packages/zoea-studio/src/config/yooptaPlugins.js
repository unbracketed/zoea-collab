/**
 * Yoopta-Editor plugin configuration.
 *
 * This file configures the plugins used by the YooptaEditor component.
 * Each plugin adds a specific block type to the editor (headings, lists, code, etc.).
 *
 * @see https://yoopta.dev/
 */

import Paragraph from '@yoopta/paragraph';
import Headings from '@yoopta/headings';
import { BulletedList, NumberedList, TodoList } from '@yoopta/lists';
import Blockquote from '@yoopta/blockquote';
import Code from '@yoopta/code';
import Link from '@yoopta/link';
import Image from '@yoopta/image';
import Divider from '@yoopta/divider';

/**
 * Array of Yoopta plugins to use in the editor.
 * Order matters - it affects the action menu display order.
 */
export const plugins = [
  Paragraph,
  Headings.HeadingOne,
  Headings.HeadingTwo,
  Headings.HeadingThree,
  BulletedList,
  NumberedList,
  TodoList,
  Blockquote,
  Code,
  Link,
  Image,
  Divider,
];

/**
 * Plugin configuration options.
 * Can be extended to customize individual plugin behavior.
 */
export const pluginOptions = {
  // Image upload configuration (to be wired to backend)
  image: {
    // onUpload will be configured in the component
  },
};

/**
 * Marks (inline formatting) configuration.
 * These are the inline styles available in the editor.
 */
export const MARKS = ['bold', 'italic', 'underline', 'strike', 'code', 'highlight'];

export default plugins;
