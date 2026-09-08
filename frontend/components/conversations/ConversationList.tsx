"use client";

import { ConversationListItem } from "@/components/conversations/ConversationListItem";
import type { Conversation } from "@/lib/types";

type ConversationListProps = {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyMessage?: string;
};

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
  loading = false,
  error = null,
  onRetry,
  emptyMessage = "No conversations found",
}: ConversationListProps) {
  if (loading) {
    return (
      <p className="px-4 py-8 text-center text-sm text-[var(--signal-muted)]">
        Loading conversations…
      </p>
    );
  }

  if (error) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="text-sm text-red-600">{error}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 text-sm font-medium text-[var(--signal-blue)]"
          >
            Try again
          </button>
        ) : null}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <p className="text-[14px] font-semibold">{emptyMessage}</p>
        {emptyMessage === "No chats" ? (
          <p className="mt-1 text-[13px] text-[var(--signal-muted)]">
            Recent chats will appear here.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
      {conversations.map((conversation) => (
        <ConversationListItem
          key={conversation.id}
          conversation={conversation}
          selected={conversation.id === selectedId}
          onSelect={onSelect}
        />
      ))}
    </nav>
  );
}
