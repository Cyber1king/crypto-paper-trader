import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/components/app-shell';
import { Dashboard } from '@/pages/dashboard';
import { Journal } from '@/pages/journal';
import { Market } from '@/pages/market';
import { Portfolio } from '@/pages/portfolio';
import { Research } from '@/pages/research';
import { Safety } from '@/pages/safety';
import { Signals } from '@/pages/signals';
import { MoneyManagement } from '@/pages/money-management';
import { Strategy } from '@/pages/strategy';
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
        <AppShell>
          <Switch>
            <Route path="/" component={Dashboard} />
            <Route path="/market" component={Market} />
            <Route path="/money-management" component={MoneyManagement} />
            <Route path="/portfolio" component={Portfolio} />
            <Route path="/journal" component={Journal} />
            <Route path="/signals" component={Signals} />
            <Route path="/strategy" component={Strategy} />
            <Route path="/research" component={Research} />
            <Route path="/safety" component={Safety} />
            <Route>
              <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-sans">
                <div className="text-center">
                  <h1 className="text-4xl font-bold font-mono text-primary mb-2">404</h1>
                  <p className="text-muted-foreground uppercase tracking-widest text-sm font-bold">Module Not Found</p>
                </div>
              </div>
            </Route>
          </Switch>
        </AppShell>
      </WouterRouter>
    </QueryClientProvider>
  );
}

export default App;
