import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, LoaderCircle, MessageSquare, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  getDefaultApi,
  type AssistantMessage,
  type AssistantPendingAction,
} from '@/lib/api';

function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message);
  }
  return error instanceof Error ? error.message : 'The request failed. Please try again.';
}

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function actionSummary(data: unknown): string {
  if (typeof data === 'string' && data.trim()) return data;
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    if (typeof record.summary === 'string') return record.summary;
    if (typeof record.message === 'string') return record.message;
  }
  return 'Action completed.';
}

function ConfirmationCard({
  action,
  message,
  onConfirm,
  onCancel,
  busy,
}: {
  action: AssistantPendingAction;
  message: AssistantMessage;
  onConfirm: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  if (message.confirmed) {
    return <p className="mt-3 text-sm font-medium text-emerald-600">Done ✓ {actionSummary(message.confirm_result)}</p>;
  }
  if (message.cancelled) {
    return <p className="mt-3 text-sm text-muted-foreground">Cancelled</p>;
  }
  if (message.confirm_error) {
    return <p className="mt-3 text-sm text-destructive">Failed: {message.confirm_error}</p>;
  }

  const args = Object.entries(action.args ?? {});
  return (
    <section className="mt-3 rounded-lg border border-primary/30 bg-background/70 p-3" aria-label="Confirm proposed action">
      <h3 className="text-sm font-semibold">{action.description || `Confirm ${action.tool_name}`}</h3>
      {args.length > 0 && (
        <div className="mt-2 overflow-hidden rounded border">
          <table className="w-full text-left text-xs">
            <tbody>
              {args.map(([key, value]) => (
                <tr key={key} className="border-b last:border-0">
                  <th className="w-2/5 px-2 py-1.5 font-mono font-medium text-muted-foreground">{key}</th>
                  <td className="break-all px-2 py-1.5">{displayValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={onConfirm}>
          {busy ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : <Check aria-hidden="true" />}
          Confirm
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </section>
  );
}

export function AssistantPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyConfirmations, setBusyConfirmations] = useState<number[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setError(null);
    try {
      const response = await getDefaultApi().getAssistantHistory();
      setMessages(response.messages);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void loadHistory();
  }, [open, loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || loading) return;
    setInput('');
    setError(null);
    const userMessage: AssistantMessage = { role: 'user', content };
    const priorMessages = messages;
    setMessages((current) => [...current, userMessage]);
    setLoading(true);
    await getDefaultApi().postAssistantHistory(userMessage).catch(() => undefined);

    try {
      const response = await getDefaultApi().sendAssistantChat({
        message: content,
        history: priorMessages,
      });
      const assistantMessage: AssistantMessage = {
        role: 'assistant',
        content: response.reply,
        pending_action: response.pending_action,
      };
      setMessages((current) => [...current, assistantMessage]);
      await getDefaultApi().postAssistantHistory(assistantMessage).catch(() => undefined);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  };

  const resolveAction = async (index: number, action: AssistantPendingAction) => {
    setBusyConfirmations((current) => [...current, index]);
    try {
      const response = await getDefaultApi().confirmAssistantAction({
        confirmation_id: action.confirmation_id,
        tool_name: action.tool_name,
        args: action.args,
      });
      setMessages((current) => current.map((message, messageIndex) => messageIndex === index
        ? response.ok
          ? { ...message, confirmed: true, confirm_result: response.data }
          : { ...message, confirm_error: response.error || 'The action was not completed.' }
        : message));
    } catch (cause) {
      setMessages((current) => current.map((message, messageIndex) => messageIndex === index
        ? { ...message, confirm_error: errorMessage(cause) }
        : message));
    } finally {
      setBusyConfirmations((current) => current.filter((busyIndex) => busyIndex !== index));
    }
  };

  const cancelAction = (index: number) => {
    // Confirmation state is UI-only in Phase C: history is append-only and keeps the original proposal.
    setMessages((current) => current.map((message, messageIndex) => messageIndex === index
      ? { ...message, cancelled: true }
      : message));
  };

  const clearHistory = async () => {
    if (!window.confirm('Clear the assistant conversation history?')) return;
    setError(null);
    try {
      await getDefaultApi().clearAssistantHistory();
      setMessages([]);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100]" role="presentation">
      <button
        type="button"
        aria-label="Close assistant"
        className="absolute inset-0 h-full w-full cursor-default bg-black/50"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Assistant"
        className="absolute inset-y-0 right-0 flex w-full max-w-[500px] flex-col border-l bg-background text-foreground shadow-2xl sm:w-[min(400px,90vw)]"
      >
        <header className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="font-semibold">Assistant</h2>
          </div>
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="sm" onClick={() => void clearHistory()}>Clear history</Button>
            <Button type="button" variant="ghost" size="icon" aria-label="Close assistant" onClick={onClose}>
              <X aria-hidden="true" />
            </Button>
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
          {historyLoading && <p className="text-sm text-muted-foreground">Loading conversation…</p>}
          {!historyLoading && messages.length === 0 && !error && (
            <p className="text-sm text-muted-foreground">Ask about your paper trading workspace.</p>
          )}
          {messages.map((message, index) => (
            <div key={`${message.timestamp ?? 'message'}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={message.role === 'user'
                ? 'max-w-[88%] whitespace-pre-wrap rounded-xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground'
                : 'max-w-[92%] whitespace-pre-wrap rounded-xl rounded-bl-sm border bg-card px-3 py-2 text-sm text-card-foreground'}>
                {message.content}
                {message.role === 'assistant' && message.pending_action && (
                  <ConfirmationCard
                    action={message.pending_action}
                    message={message}
                    busy={busyConfirmations.includes(index)}
                    onConfirm={() => void resolveAction(index, message.pending_action!)}
                    onCancel={() => cancelAction(index)}
                  />
                )}
              </div>
            </div>
          ))}
          {loading && <p className="text-sm text-muted-foreground">Assistant is thinking…</p>}
          {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          <div ref={bottomRef} />
        </div>

        <form
          className="flex items-end gap-2 border-t p-3"
          onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}
        >
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Message the assistant…"
            aria-label="Message the assistant"
            rows={2}
            disabled={loading}
            className="max-h-32 min-h-10 resize-y text-sm"
          />
          <Button type="submit" disabled={loading || !input.trim()} aria-label="Send message">
            Send
          </Button>
        </form>
      </aside>
    </div>
  );
}
