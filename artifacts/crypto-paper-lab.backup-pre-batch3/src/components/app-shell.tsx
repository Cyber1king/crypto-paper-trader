import { useEffect, useState, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Link, useLocation } from 'wouter';
import {
  Activity,
  BookOpen,
  FileText,
  LayoutDashboard,
  Menu,
  Radio,
  ShieldCheck,
  Wallet,
  X,
  type LucideIcon,
} from 'lucide-react';

interface NavItem {
  readonly key: string;
  readonly label: string;
  /** `null` marks a screen that is planned but has no route yet. */
  readonly href: string | null;
  readonly icon: LucideIcon;
}

// Only routes that exist in App.tsx carry an href. Everything else is disabled
// rather than linked, so the shell never navigates to a 404 or implies a
// working screen that has not been built.
const NAV_ITEMS: readonly NavItem[] = [
  { key: 'overview', label: 'Overview', href: '/', icon: LayoutDashboard },
  { key: 'market', label: 'Market analysis', href: null, icon: Activity },
  { key: 'signals', label: 'Strategy signals', href: null, icon: Radio },
  { key: 'portfolio', label: 'Paper portfolio', href: '/portfolio', icon: Wallet },
  { key: 'journal', label: 'Trade journal', href: '/journal', icon: BookOpen },
  { key: 'reports', label: 'Research reports', href: null, icon: FileText },
  { key: 'safety', label: 'Research safety', href: null, icon: ShieldCheck },
];

function NavList({
  idPrefix,
  onNavigate,
}: {
  idPrefix: string;
  onNavigate?: () => void;
}) {
  const [location] = useLocation();

  return (
    <nav aria-label="Primary" data-testid={`${idPrefix}-nav`}>
      <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        Screens
      </p>
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;

          if (item.href === null) {
            return (
              <li key={item.key}>
                <span
                  aria-disabled="true"
                  data-testid={`${idPrefix}-nav-${item.key}`}
                  className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 truncate">{item.label}</span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-widest">
                    Planned
                  </span>
                </span>
              </li>
            );
          }

          const active = location === item.href;

          return (
            <li key={item.key}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? 'page' : undefined}
                data-testid={`${idPrefix}-nav-${item.key}`}
                className={active
                  ? 'flex items-center gap-3 rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-sm font-semibold text-primary'
                  : 'flex items-center gap-3 rounded-md border border-transparent px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground'}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // If the viewport grows past the mobile breakpoint while the drawer is open,
  // close it so the scroll lock and overlay do not outlive the mobile layout.
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;

    const query = window.matchMedia('(min-width: 768px)');
    const closeOnDesktop = () => {
      if (query.matches) setDrawerOpen(false);
    };

    query.addEventListener('change', closeOnDesktop);
    return () => query.removeEventListener('change', closeOnDesktop);
  }, []);

  return (
    <div
      className="flex min-h-screen bg-background text-foreground font-sans"
      data-testid="app-shell"
    >
      {/* Desktop: persistent sidebar */}
      <aside
        className="sticky top-0 hidden h-screen w-56 shrink-0 self-start overflow-y-auto border-r bg-card p-3 md:block"
        data-testid="shell-sidebar"
      >
        <NavList idPrefix="shell-desktop" />
      </aside>

      {/* Mobile: floating trigger plus drawer */}
      <Dialog.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <Dialog.Trigger asChild>
          <button
            type="button"
            aria-label="Open navigation"
            data-testid="shell-mobile-open"
            className="fixed bottom-4 left-4 z-40 flex h-11 w-11 items-center justify-center rounded-full border bg-card text-foreground shadow-md md:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 md:hidden" />
          <Dialog.Content
            data-testid="shell-drawer"
            className="fixed inset-y-0 left-0 z-50 flex w-64 max-w-[85vw] flex-col gap-3 overflow-y-auto border-r bg-card p-3 shadow-lg focus:outline-none md:hidden"
          >
            <div className="flex items-center justify-between px-1">
              <Dialog.Title className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Navigation
              </Dialog.Title>
              <Dialog.Close asChild>
                <button
                  type="button"
                  aria-label="Close navigation"
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </Dialog.Close>
            </div>
            <Dialog.Description className="sr-only">
              Choose a screen.
            </Dialog.Description>
            <NavList
              idPrefix="shell-mobile"
              onNavigate={() => setDrawerOpen(false)}
            />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}