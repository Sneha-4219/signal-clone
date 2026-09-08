import type { ConversationOut } from "@/lib/api";
import { formatLastSeen } from "@/lib/format-last-seen";
import type { Conversation, ConversationKind } from "@/lib/types";

const ACCENTS = ["#3a76f0", "#0f9d58", "#7c4dff", "#e67e22", "#d81b60"];

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return "Yesterday";
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  }
  return name.trim().slice(0, 2).toUpperCase() || "?";
}

export function toConversation(row: ConversationOut, currentUserId?: number): Conversation {
  const kind: ConversationKind = row.type === "group" ? "group" : "direct";
  const name =
    kind === "direct"
      ? (row.other_user?.display_name ?? "Unknown")
      : (row.name ?? "Group");
  const lastSeen =
    kind === "direct" && row.other_user?.last_seen
      ? formatLastSeen(row.other_user.last_seen)
      : kind === "direct"
        ? "offline"
        : undefined;

  return {
    id: String(row.id),
    kind,
    name,
    initials: initialsFromName(name),
    accent: ACCENTS[row.id % ACCENTS.length] ?? ACCENTS[0],
    preview: "No messages yet",
    timestamp: formatTimestamp(row.updated_at),
    unread: 0,
    online: kind === "direct" ? Boolean(row.other_user?.is_online) : undefined,
    lastSeen,
    otherUserId: kind === "direct" ? (row.other_user?.id ?? null) : null,
    memberCount: kind === "group" ? row.members.length : undefined,
    myRole:
      kind === "group" && currentUserId != null
        ? row.members.find((member) => member.user_id === currentUserId)?.role
        : undefined,
    memberNames:
      kind === "group"
        ? Object.fromEntries(
            row.members.map((member) => [member.user_id, member.user.display_name]),
          )
        : undefined,
    typing: false,
    typingUserIds: [],
    avatarUrl: kind === "direct" ? row.other_user?.avatar_url : null,
  };
}
