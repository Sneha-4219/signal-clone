"use client";

import { Avatar } from "@/components/common/Avatar";
import type { Conversation } from "@/lib/types";

type ConversationListItemProps = {
  conversation: Conversation;
  selected: boolean;
  onSelect: (id: string) => void;
};

export function ConversationListItem({
  conversation,
  selected,
  onSelect,
}: ConversationListItemProps) {
  const unread = conversation.unread > 0;
  return (
    <div className="px-2 py-[1px]">
      <button
        type="button"
        onClick={() => onSelect(conversation.id)}
        className={`flex w-full min-w-0 items-center gap-2.5 rounded-lg px-2 py-[7px] text-left ${
          selected ? "bg-[var(--signal-selected)]" : "hover:bg-[var(--signal-hover)]"
        }`}
      >
        <Avatar
          initials={conversation.initials}
          accent={conversation.accent}
          size="sm"
          online={conversation.kind === "direct" ? conversation.online : false}
          src={conversation.avatarUrl}
        />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span
              className={`truncate text-[13px] leading-5 ${
                unread ? "font-semibold text-[var(--signal-text)]" : "font-medium text-[var(--signal-text)]"
              }`}
            >
              {conversation.name}
            </span>
            <span
              className={`shrink-0 text-[11px] leading-5 ${
                unread ? "font-medium text-[var(--signal-blue)]" : "text-[var(--signal-muted)]"
              }`}
            >
              {conversation.timestamp}
            </span>
          </span>
          <span className="mt-px flex min-w-0 items-center justify-between gap-2">
            <span
              className={`min-w-0 flex-1 truncate text-[12px] leading-4 ${
                conversation.typing
                  ? "text-[var(--signal-blue)]"
                  : unread
                    ? "text-[var(--signal-text)]"
                    : "text-[var(--signal-muted)]"
              }`}
            >
              {conversation.typing ? "Typing…" : conversation.preview}
            </span>
            {unread ? (
              <span
                aria-label={`${conversation.unread} unread`}
                className="inline-flex h-[18px] min-w-[18px] shrink-0 items-center justify-center rounded-full bg-[var(--signal-blue)] px-1.5 text-[10px] font-semibold leading-none text-white"
              >
                {conversation.unread}
              </span>
            ) : null}
          </span>
        </span>
      </button>
    </div>
  );
}
