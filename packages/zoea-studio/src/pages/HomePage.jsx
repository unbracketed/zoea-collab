import { useNavigate } from 'react-router-dom';
import LayoutFrame from '../components/layout/LayoutFrame';
import { useAuthStore, useWorkspaceStore } from '../stores';

function HomePage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const projects = useWorkspaceStore((state) => state.projects);

  const handleGetStarted = () => {
    navigate('/dashboard');
  };

  const handleExploreDocuments = () => {
    navigate('/documents');
  };

  const handleStartChat = () => {
    navigate('/chat');
  };

  return (
    <LayoutFrame title="Home" variant="content-centered">
      <div className="home-page">
        <div className="home-content">
          <div className="home-logo">
            <svg viewBox="0 0 200 200" className="zoea-logo">
              <circle cx="100" cy="100" r="80" fill="#2563eb" opacity="0.1" />
              <circle cx="100" cy="100" r="60" fill="#2563eb" opacity="0.2" />
              <circle cx="100" cy="100" r="40" fill="#2563eb" opacity="0.3" />
              <circle cx="100" cy="100" r="20" fill="#2563eb" />
              <path
                d="M 60 100 Q 100 60, 140 100 Q 100 140, 60 100"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="3"
              />
              <path
                d="M 100 60 Q 140 100, 100 140 Q 60 100, 100 60"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="3"
              />
            </svg>
          </div>
          <h1 className="home-title">Welcome to Zoea Studio</h1>
          {user && (
            <p className="home-subtitle">
              Hello, {user.username}! Let&apos;s get started.
            </p>
          )}

          <div className="home-actions">
            {projects.length > 0 && (
              <div className="home-project-info">
                <p className="home-project-label">
                  You have access to {projects.length} project{projects.length !== 1 ? 's' : ''}
                </p>
              </div>
            )}

            <div className="home-buttons">
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={handleGetStarted}
              >
                Go to Dashboard
              </button>
              <button
                type="button"
                className="btn btn-outline-primary btn-lg"
                onClick={handleExploreDocuments}
              >
                Explore Documents
              </button>
              <button
                type="button"
                className="btn btn-outline-secondary btn-lg"
                onClick={handleStartChat}
              >
                Start a Chat
              </button>
            </div>
          </div>

          <div className="home-tips">
            <h3>Quick Tips</h3>
            <ul>
              <li>
                <strong>Documents:</strong> Upload and organize your files, images, and diagrams
              </li>
              <li>
                <strong>Chat:</strong> Have AI-powered conversations with context from your documents
              </li>
              <li>
                <strong>Canvas:</strong> Create visual diagrams and concept maps
              </li>
              <li>
                <strong>Flows:</strong> Run automated workflows on your documents
              </li>
            </ul>
          </div>
        </div>
      </div>
    </LayoutFrame>
  );
}

export default HomePage;
