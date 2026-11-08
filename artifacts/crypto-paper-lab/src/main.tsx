import { createRoot } from 'react-dom/client';

import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';
import { ThemeProvider } from '@/lib/theme';
import { AssistantProvider } from '@/lib/assistant-context';

import './index.css';

createRoot(document.getElementById('root')!, {
  // Keeps caught errors off reportError(), which would raise the dev overlay.
  onCaughtError: (error, errorInfo) => {
    console.error(error, errorInfo.componentStack);
  },
}).render(
  <ThemeProvider>
    <AssistantProvider>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </AssistantProvider>
  </ThemeProvider>,
);
