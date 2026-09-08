export type MessageStatus = "sending" | "sent" | "delivered" | "read";

export type ConversationKind = "direct" | "group";

export type Conversation = {
  id: string;
  kind: ConversationKind;
  name: string;
  initials: string;
  accent: string;
  preview: string;
  timestamp: string;
  unread: number;
  online?: boolean;
  lastSeen?: string;
  otherUserId?: number | null;
  memberCount?: number;
  myRole?: string;
  memberNames?: Record<number, string>;
  typing?: boolean;
  typingUserIds?: number[];
  avatarUrl?: string | null;
};

/** Optional quoted preview when a message is a reply. Not populated unless reply data exists. */
export type ChatMessageReply = {
  senderName?: string | null;
  content: string;
};

export type ChatMessage = {
  id: string;
  conversationId: string;
  senderId: number | null;
  senderDisplayName?: string | null;
  fromMe: boolean;
  content: string;
  timestamp: string;
  status?: MessageStatus;
  replyTo?: ChatMessageReply | null;
};
