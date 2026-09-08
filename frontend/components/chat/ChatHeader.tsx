"use client";

import { ArrowLeft, MoreHorizontal, Phone, Search, Users, Video } from "lucide-react";
import { Avatar } from "@/components/common/Avatar";
import type { Conversation } from "@/lib/types";

type ChatHeaderProps = {
  conversation: Conversation;
  onBack?: () => void;
  onPlaceholder: (label: string) => void;
  onGroupInfo?: () => void;
};

export function ChatHeader({ conversation, onBack, onPlaceholder, onGroupInfo }: ChatHeaderProps) {
  const subtitle =
    conversation.kind === "group"
      ? `${conversation.memberCount ?? 0} members`
      : conversation.online
        ? "online"
        : (conversation.lastSeen ?? "offline");

  return (
    <header className="flex h-12 shrink-0 items-center gap-2.5 border-b border-[var(--signal-border)] bg-[var(--signal-panel)] px-4">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to conversations"
          title="Back to conversations"
          className="icon-btn md:hidden"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
      ) : null}
      <Avatar
        initials={conversation.initials}
        accent={conversation.accent}
        size="sm"
        online={conversation.kind === "direct" ? conversation.online : false}
        src={conversation.avatarUrl}
      />
      {conversation.kind === "group" ? (
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={onGroupInfo}
        >
          <h2 className="truncate text-[14px] font-semibold leading-5 text-[var(--signal-text)]">
            {conversation.name}
          </h2>
          <p className="truncate text-[12px] leading-4 text-[var(--signal-muted)]">{subtitle}</p>
        </button>
      ) : (
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[14px] font-semibold leading-5 text-[var(--signal-text)]">
            {conversation.name}
          </h2>
          <p className="truncate text-[12px] leading-4 text-[var(--signal-muted)]">{subtitle}</p>
        </div>
      )}
      <div className="flex shrink-0 items-center gap-0.5">
        {conversation.kind === "group" ? (
          <button
            type="button"
            onClick={() => (onGroupInfo ? onGroupInfo() : onPlaceholder("Group members"))}
            aria-label="Group members"
            title="Group members"
            className="icon-btn"
          >
            <Users className="h-[18px] w-[18px]" />
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onPlaceholder("Video calls")}
          aria-label="Video calls"
          title="Video calls"
          className="icon-btn"
        >
          <Video className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          onClick={() => onPlaceholder("Voice calls")}
          aria-label="Voice calls"
          title="Voice calls"
          className="icon-btn"
        >
          <Phone className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          onClick={() => onPlaceholder("Search conversation")}
          aria-label="Search"
          title="Search"
          className="icon-btn"
        >
          <Search className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          onClick={() => onPlaceholder("Conversation settings")}
          aria-label="Conversation settings"
          title="Conversation settings"
          className="icon-btn"
        >
          <MoreHorizontal className="h-[18px] w-[18px]" />
        </button>
      </div>
    </header>
  );
}
