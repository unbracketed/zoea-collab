import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import './App.css';
import AppRoutes from './Routes';
import { useThemeStore } from './stores';

function App() {
  const initializeTheme = useThemeStore((state) => state.initialize);

  useEffect(() => {
    initializeTheme();
  }, [initializeTheme]);

  return (
    <>
      <AppRoutes />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: 'var(--surface)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          },
          success: {
            iconTheme: {
              primary: 'var(--success-color, #198754)',
              secondary: 'white',
            },
          },
          error: {
            iconTheme: {
              primary: 'var(--danger-color, #dc3545)',
              secondary: 'white',
            },
          },
        }}
      />
    </>
  );
}

export default App;
