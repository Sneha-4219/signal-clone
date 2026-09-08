"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WS_BASE, type MessageOut } from "@/lib/api";
import { toChatMessage } from "@/lib/map-message";
import type { ChatMessage } from "@/lib/types";

export type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";

export type ReceiptEvent = {
  messageId: number;
  userId: number;
  status: string;
};

export type TypingEvent = {
  conversationId: string;
  userId: number;
  isTyping: boolean;
};

export type PresenceEvent = {
  conversationId: string;
  userId: number;
  isOnline: boolean;
  lastSeen: string | null;
};

export type GroupMembershipEvent = {
  action: "added" | "removed";
  conversationId: string;
  userId: number;
};

type ServerEvent = {
  type?: string;
  message?: MessageOut;
  message_id?: number;
  user_id?: number;
  conversation_id?: number;
  status?: string;
  is_typing?: boolean;
  is_online?: boolean;
  last_seen?: string | null;
  user?: { user_id?: number };
  detail?: string;
};

export function conversationSocketUrl(conversationId: number): string {
  return `${WS_BASE}/ws/conversations/${conversationId}`;
}

export function useConversationSockets(
  conversationIds: number[],
  currentUserId: number | undefined,
  onMessage: (message: ChatMessage) => void,
  onReceipt: (receipt: ReceiptEvent) => void,
  onTyping: (event: TypingEvent) => void,
  onPresence: (event: PresenceEvent) => void,
  onMembership: (event: GroupMembershipEvent) => void,
): {
  statuses: Record<number, SocketStatus>;
  sendClientEvent: (conversationId: number, payload: object) => boolean;
} {
  const [statuses, setStatuses] = useState<Record<number, SocketStatus>>({});
  const onMessageRef = useRef(onMessage);
  const onReceiptRef = useRef(onReceipt);
  const onTypingRef = useRef(onTyping);
  const onPresenceRef = useRef(onPresence);
  const onMembershipRef = useRef(onMembership);
  const socketsRef = useRef(new Map<number, WebSocket>());
  const currentUserIdRef = useRef(currentUserId);
  const idsKey = [...conversationIds].sort((left, right) => left - right).join(",");

  useEffect(() => {
    currentUserIdRef.current = currentUserId;
  }, [currentUserId]);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    onReceiptRef.current = onReceipt;
  }, [onReceipt]);

  useEffect(() => {
    onTypingRef.current = onTyping;
  }, [onTyping]);

  useEffect(() => {
    onPresenceRef.current = onPresence;
  }, [onPresence]);

  useEffect(() => {
    onMembershipRef.current = onMembership;
  }, [onMembership]);

  useEffect(() => {
    if (currentUserId == null || !idsKey) {
      return;
    }

    const ids = idsKey
      .split(",")
      .map((value) => Number(value))
      .filter((id) => Number.isInteger(id) && id > 0);
    let cancelled = false;
    const sockets = new Map<number, WebSocket>();
    socketsRef.current = sockets;

    function setSocketStatus(id: number, status: SocketStatus) {
      if (!cancelled) {
        setStatuses((current) =>
          current[id] === status ? current : { ...current, [id]: status },
        );
      }
    }

    for (const id of ids) {
      const socket = new WebSocket(conversationSocketUrl(id));
      sockets.set(id, socket);
      socket.onopen = () => {
        setSocketStatus(id, "open");
      };
      socket.onclose = (event) => {
        onTypingRef.current({
          conversationId: String(id),
          userId: 0,
          isTyping: false,
        });
        if (event.code === 4403) {
          const selfId = currentUserIdRef.current;
          if (selfId != null) {
            onMembershipRef.current({
              action: "removed",
              conversationId: String(id),
              userId: selfId,
            });
          }
        }
        if (cancelled) {
          return;
        }
        setSocketStatus(id, event.code === 1000 ? "closed" : "error");
      };
      socket.onmessage = (event) => {
        if (cancelled) {
          return;
        }
        let payload: ServerEvent;
        try {
          payload = JSON.parse(event.data) as ServerEvent;
        } catch {
          return;
        }
        if (payload.type === "message" && payload.message) {
          onMessageRef.current(toChatMessage(payload.message, currentUserIdRef.current));
          return;
        }
        if (
          payload.type === "receipt" &&
          typeof payload.message_id === "number" &&
          typeof payload.status === "string"
        ) {
          onReceiptRef.current({
            messageId: payload.message_id,
            userId: typeof payload.user_id === "number" ? payload.user_id : 0,
            status: payload.status,
          });
          return;
        }
        if (payload.type === "typing" && typeof payload.is_typing === "boolean") {
          onTypingRef.current({
            conversationId: String(id),
            userId: typeof payload.user_id === "number" ? payload.user_id : 0,
            isTyping: payload.is_typing,
          });
          return;
        }
        if (payload.type === "presence" && typeof payload.user_id === "number") {
          onPresenceRef.current({
            conversationId: String(id),
            userId: payload.user_id,
            isOnline: Boolean(payload.is_online),
            lastSeen: payload.last_seen ?? null,
          });
          return;
        }
        if (payload.type === "group_member_added") {
          const userId = payload.user?.user_id ?? payload.user_id;
          if (typeof userId === "number") {
            onMembershipRef.current({
              action: "added",
              conversationId: String(payload.conversation_id ?? id),
              userId,
            });
          }
          return;
        }
        if (payload.type === "group_member_removed" && typeof payload.user_id === "number") {
          onMembershipRef.current({
            action: "removed",
            conversationId: String(payload.conversation_id ?? id),
            userId: payload.user_id,
          });
        }
      };
    }

    return () => {
      cancelled = true;
      if (socketsRef.current === sockets) {
        socketsRef.current = new Map();
      }
      for (const id of ids) {
        onTypingRef.current({
          conversationId: String(id),
          userId: 0,
          isTyping: false,
        });
      }
      for (const socket of sockets.values()) {
        socket.onopen = null;
        socket.onclose = null;
        socket.onmessage = null;
        if (
          socket.readyState === WebSocket.OPEN ||
          socket.readyState === WebSocket.CONNECTING
        ) {
          socket.close();
        }
      }
    };
  }, [idsKey, currentUserId]);

  const sendClientEvent = useCallback((conversationId: number, payload: object) => {
    const socket = socketsRef.current.get(conversationId);
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  return { statuses, sendClientEvent };
}
