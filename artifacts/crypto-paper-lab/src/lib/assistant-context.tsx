import { createContext, useContext, useState, type ReactNode } from 'react';
import { AssistantPanel } from '@/components/assistant-panel';

interface AssistantContextValue {
  isOpen: boolean;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

export const AssistantContext = createContext<AssistantContextValue | null>(null);

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const value: AssistantContextValue = {
    isOpen,
    toggle: () => setIsOpen((current) => !current),
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
  };

  return (
    <AssistantContext.Provider value={value}>
      {children}
      <AssistantPanel open={isOpen} onClose={() => setIsOpen(false)} />
    </AssistantContext.Provider>
  );
}

export function useAssistant(): AssistantContextValue {
  const context = useContext(AssistantContext);
  if (!context) {
    throw new Error('useAssistant must be used within an AssistantProvider');
  }
  return context;
}
