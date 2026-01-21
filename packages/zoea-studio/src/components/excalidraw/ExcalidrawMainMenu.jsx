/**
 * Custom MainMenu for Excalidraw
 *
 * Replaces the default Excalidraw menu with project-specific options
 * for inserting documents, images, and accessing AI features.
 */

import { MainMenu } from '@excalidraw/excalidraw';
import { FileText, Image, Sparkles, Frame } from 'lucide-react';

export default function ExcalidrawMainMenu({
  onInsertDocument,
  onInsertImage,
  onOpenAIChat,
  onCreateAIFrame,
}) {
  return (
    <MainMenu>
      <MainMenu.Group title="Project">
        <MainMenu.Item
          onSelect={onInsertDocument}
          icon={<FileText className="h-4 w-4" />}
        >
          Insert Document
        </MainMenu.Item>
        <MainMenu.Item
          onSelect={onInsertImage}
          icon={<Image className="h-4 w-4" />}
        >
          Insert Image
        </MainMenu.Item>
      </MainMenu.Group>

      <MainMenu.Group title="AI">
        <MainMenu.Item
          onSelect={onOpenAIChat}
          icon={<Sparkles className="h-4 w-4" />}
        >
          AI Chat Sidebar
        </MainMenu.Item>
        <MainMenu.Item
          onSelect={onCreateAIFrame}
          icon={<Frame className="h-4 w-4" />}
        >
          Create AI Prompt Frame
        </MainMenu.Item>
      </MainMenu.Group>

      <MainMenu.Separator />

      <MainMenu.DefaultItems.Export />
      <MainMenu.DefaultItems.SaveAsImage />
      <MainMenu.DefaultItems.ClearCanvas />
      <MainMenu.DefaultItems.ToggleTheme />
      <MainMenu.DefaultItems.ChangeCanvasBackground />
    </MainMenu>
  );
}
