import type { MessageReceiptOut } from "@/lib/api";
import { isOwnMessage, readMessageSenderId } from "@/lib/message-ownership";
import type { ChatMessage, MessageStatus } from "@/lib/types";

const STATUS_RANK: Record<MessageStatus, number> = {
  sending: 0,
  sent: 1,
  delivered: 2,
  read: 3,
};

export function advanceStatus(
  current: MessageStatus | undefined,
  incoming: string,
): MessageStatus {
  const next = toBubbleStatus(incoming) ?? "sent";
  if (!current || STATUS_RANK[next] > STATUS_RANK[current]) {
    return next;
  }
  return current;
}

function senderStatusFromReceipts(receipts: MessageReceiptOut[]): MessageStatus {
  let best: MessageStatus = "sent";
  for (const receipt of receipts) {
    best = advanceStatus(best, receipt.status);
  }
  return best;
}

function formatMessageTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const now = new Date();
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (date.toDateString() === now.toDateString()) {
    return time;
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday ${time}`;
  }
  return `${date.toLocaleDateString([], { month: "short", day: "numeric" })} ${time}`;
}

function toBubbleStatus(status: string): MessageStatus | undefined {
  if (status === "sending" || status === "sent" || status === "delivered" || status === "read") {
    return status;
  }
  return undefined;
}

export function toChatMessage(
  row: {
    id: unknown;
    conversation_id: unknown;
    sender_id?: unknown;
    sender?: { id?: unknown; display_name?: unknown } | null;
    content: string;
    created_at: string;
    receipts?: MessageReceiptOut[] | null;
  },
  currentUserId: unknown,
): ChatMessage {
  const senderId = readMessageSenderId(row);
  const fromMe = isOwnMessage(senderId, currentUserId);
  const senderDisplayName =
    typeof row.sender?.display_name === "string" && row.sender.display_name.trim()
      ? row.sender.display_name.trim()
      : null;
  return {
    id: String(row.id),
    conversationId: String(row.conversation_id),
    senderId,
    senderDisplayName,
    fromMe,
    content: row.content,
    timestamp: formatMessageTime(row.created_at),
    status: fromMe
      ? senderStatusFromReceipts(row.receipts ?? [])
      : undefined,
  };
}
