"use client";

import { useEffect } from "react";

type ToastProps = {
  message: string;
  onDismiss: () => void;
};

export function Toast({ message, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, 4000);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  return (
    <div
      role="status"
      className="fixed right-4 bottom-4 z-50 max-w-xs rounded-md border border-[var(--signal-border)] bg-[var(--signal-panel)] px-3 py-2 text-[13px] shadow-sm"
    >
      <p>{message}</p>
      <button
        type="button"
        className="mt-2 text-xs font-medium text-[var(--signal-blue)]"
        onClick={onDismiss}
      >
        Dismiss
      </button>
    </div>
  );
}
