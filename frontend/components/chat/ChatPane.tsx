"use client";

import { useEffect, useRef } from "react";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { MessageComposer } from "@/components/chat/MessageComposer";
import { ChatHeader } from "@/components/chat/ChatHeader";
import type { ChatMessage, Conversation } from "@/lib/types";
import { isOwnMessage } from "@/lib/message-ownership";

type ChatPaneProps = {
  conversation: Conversation;
  messages: ChatMessage[];
  currentUserId: number;
  onSend: (content: string) => Promise<void>;
  onBack?: () => void;
  onPlaceholder: (label: string) => void;
  onGroupInfo?: () => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  sending?: boolean;
  sendError?: string | null;
  liveStatus?: string | null;
  typingLabel?: string | null;
  onTypingChange?: (isTyping: boolean, conversationId: string) => void;
};

export function ChatPane({
  conversation,
  messages,
  currentUserId,
  onSend,
  onBack,
  onPlaceholder,
  onGroupInfo,
  loading = false,
  error = null,
  onRetry,
  sending = false,
  sendError = null,
  liveStatus = null,
  typingLabel = null,
  onTypingChange,
}: ChatPaneProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (loading) {
      return;
    }
    const node = scrollerRef.current;
    if (!node) {
      return;
    }
    requestAnimationFrame(() => {
      node.scrollTop = node.scrollHeight;
    });
  }, [loading, messages]);

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-[var(--signal-chat)]">
      <ChatHeader
        conversation={conversation}
        onBack={onBack}
        onPlaceholder={onPlaceholder}
        onGroupInfo={onGroupInfo}
      />
      <div ref={scrollerRef} className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-5 py-2.5 md:px-8">
        <div className="flex w-full min-w-0 flex-col">
          {loading ? (
            <p className="py-8 text-center text-sm text-[var(--signal-muted)]">
              Loading messages…
            </p>
          ) : error ? (
            <div className="py-8 text-center">
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
          ) : messages.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--signal-muted)]">
              No messages yet
            </p>
          ) : (
            messages.map((message, index) => {
              const previous = index > 0 ? messages[index - 1] : undefined;
              const clustered =
                previous != null && previous.senderId === message.senderId;
              return (
                <MessageBubble
                  key={message.id}
                  message={message}
                  currentUserId={currentUserId}
                  clustered={clustered}
                  senderLabel={
                    conversation.kind === "group" &&
                    !isOwnMessage(message.senderId, currentUserId)
                      ? message.senderDisplayName
                        ?? (message.senderId != null
                          ? conversation.memberNames?.[message.senderId]
                          : null)
                      : null
                  }
                />
              );
            })
          )}
        </div>
      </div>
      {liveStatus ? (
        <p className="shrink-0 bg-[var(--signal-chat)] px-3 py-1 text-[11px] text-[var(--signal-muted)]">
          {liveStatus}
        </p>
      ) : null}
      {typingLabel ? (
        <p
          aria-live="polite"
          className="shrink-0 px-4 py-1 text-[12px] text-[var(--signal-muted)] italic"
        >
          {typingLabel}
        </p>
      ) : null}
      <MessageComposer
        key={conversation.id}
        onSend={onSend}
        onPlaceholder={onPlaceholder}
        onTypingChange={
          onTypingChange
            ? (isTyping) => onTypingChange(isTyping, conversation.id)
            : undefined
        }
        disabled={loading}
        sending={sending}
        error={sendError}
      />
    </section>
  );
}
