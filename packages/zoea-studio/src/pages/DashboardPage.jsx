import LayoutFrame from '../components/layout/LayoutFrame';
import { useAuthStore } from '../stores';

function DashboardPage() {
  const user = useAuthStore((state) => state.user);

  return (
    <LayoutFrame title="Dashboard" variant="content-centered">
      <div className="dashboard-page">
        <div className="dashboard-content">
          <div className="dashboard-logo">
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
          <h1 className="dashboard-welcome">Welcome to Zoea Studio</h1>
          {user && (
            <p className="dashboard-subtitle">
              Hello, {user.username}! Ready to start creating?
            </p>
          )}
          {user?.organization && (
            <p className="dashboard-org">
              Organization: {user.organization.name}
            </p>
          )}
        </div>
      </div>
    </LayoutFrame>
  );
}

export default DashboardPage;
