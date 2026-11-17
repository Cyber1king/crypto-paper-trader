import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from '@/pages/dashboard';
import {
  Route,
  Switch,
  Router as WouterRouter,
} from 'wouter';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WouterRouter base={import.meta.env.BASE_URL?.replace(/\/$/, '') || ''}>
        <Switch>
          <Route path="/" component={Dashboard} />
          <Route>
            <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-sans">
              <div className="text-center">
                <h1 className="text-4xl font-bold font-mono text-primary mb-2">404</h1>
                <p className="text-muted-foreground uppercase tracking-widest text-sm font-bold">Module Not Found</p>
              </div>
            </div>
          </Route>
        </Switch>
      </WouterRouter>
    </QueryClientProvider>
  );
}

export default App;
