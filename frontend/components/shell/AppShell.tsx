"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Copy, MoreHorizontal, Phone, Plus, SquarePen } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { ChatPane } from "@/components/chat/ChatPane";
import { ConversationList } from "@/components/conversations/ConversationList";
import { ConversationSearch } from "@/components/conversations/ConversationSearch";
import { NewGroupDialog } from "@/components/groups/NewGroupDialog";
import { GroupInfoDialog } from "@/components/groups/GroupInfoDialog";
import { Toast } from "@/components/common/Toast";
import { SettingsDialog } from "@/components/settings/SettingsDialog";
import { NavRail, type RailSection } from "@/components/shell/NavRail";
import { TabVisibilityControls } from "@/components/shell/TabVisibilityControls";
import { WelcomePane } from "@/components/shell/WelcomePane";
import { SectionEmptyPane } from "@/components/shell/SectionEmptyPane";
import { NewChatPanel } from "@/components/shell/NewChatPanel";
import { FindContactPanel } from "@/components/shell/FindContactPanel";
import { conversationsApi, messagesApi } from "@/lib/api";
import { toConversation } from "@/lib/map-conversation";
import { advanceStatus, toChatMessage } from "@/lib/map-message";
import { isOwnMessage } from "@/lib/message-ownership";
import { formatLastSeen } from "@/lib/format-last-seen";
import { useConversationSockets } from "@/lib/use-conversation-socket";
import type { ChatMessage, Conversation } from "@/lib/types";

function mergeConversationList(
  incoming: Conversation[],
  previous: Conversation[],
): Conversation[] {
  const previousById = new Map(previous.map((item) => [item.id, item]));
  const merged = incoming.map((item) => {
    const old = previousById.get(item.id);
    if (!old) {
      return item;
    }
    return {
      ...item,
      unread: old.unread,
      preview: old.preview,
      timestamp: old.timestamp,
      online: old.online ?? item.online,
      lastSeen: old.lastSeen ?? item.lastSeen,
      typing: old.typingUserIds?.length ? true : Boolean(old.typing),
      typingUserIds: old.typingUserIds ?? item.typingUserIds,
      otherUserId: item.otherUserId ?? old.otherUserId,
    };
  });
  const mergedById = new Map(merged.map((item) => [item.id, item]));
  const keptOrder = previous
    .map((item) => mergedById.get(item.id))
    .filter((item): item is Conversation => item != null);
  if (keptOrder.length === 0) {
    return merged;
  }
  const keptIds = new Set(keptOrder.map((item) => item.id));
  const extras = merged.filter((item) => !keptIds.has(item.id));
  return [...keptOrder, ...extras];
}

function applyLiveConversation(
  current: Conversation[],
  incoming: ChatMessage,
  selectedId: string | null,
  isOwn: boolean,
  firstSeen: boolean,
): Conversation[] {
  const updated = current.map((item) => {
    if (item.id !== incoming.conversationId) {
      return item;
    }
    const unread =
      firstSeen && !isOwn && selectedId !== item.id ? item.unread + 1 : item.unread;
    return {
      ...item,
      preview: incoming.content,
      timestamp: incoming.timestamp,
      unread,
    };
  });
  const active = updated.find((item) => item.id === incoming.conversationId);
  const rest = updated.filter((item) => item.id !== incoming.conversationId);
  return active ? [active, ...rest] : updated;
}

function applyTypingState(
  current: Conversation[],
  conversationId: string,
  isTyping: boolean,
  userId: number,
): Conversation[] {
  return current.map((item) => {
    if (item.id !== conversationId) {
      return item;
    }
    if (userId < 1) {
      return { ...item, typing: false, typingUserIds: [] };
    }
    const ids = new Set(item.typingUserIds ?? []);
    if (isTyping) {
      ids.add(userId);
    } else {
      ids.delete(userId);
    }
    const typingUserIds = [...ids];
    return { ...item, typingUserIds, typing: typingUserIds.length > 0 };
  });
}

function typingLabelFor(conversation: Conversation): string | null {
  const ids = conversation.typingUserIds ?? [];
  if (!conversation.typing && ids.length === 0) {
    return null;
  }
  if (conversation.kind === "direct") {
    return `${conversation.name} is typing...`;
  }
  const names = ids
    .map((id) => conversation.memberNames?.[id])
    .filter((name): name is string => Boolean(name));
  if (names.length === 0) {
    return "Someone is typing...";
  }
  if (names.length === 1) {
    return `${names[0]} is typing...`;
  }
  if (names.length === 2) {
    return `${names[0]} and ${names[1]} are typing...`;
  }
  return `${names[0]}, ${names[1]} and ${names.length - 2} others are typing...`;
}

function applyPresenceState(
  current: Conversation[],
  userId: number,
  isOnline: boolean,
  lastSeen: string | null,
): Conversation[] {
  return current.map((item) => {
    if (item.kind !== "direct" || item.otherUserId !== userId) {
      return item;
    }
    return {
      ...item,
      online: isOnline,
      lastSeen: isOnline ? item.lastSeen : formatLastSeen(lastSeen),
    };
  });
}

function upsertChatMessage(current: ChatMessage[], incoming: ChatMessage): ChatMessage[] {
  const index = current.findIndex((item) => item.id === incoming.id);
  if (index === -1) {
    return [...current, incoming];
  }
  const previous = current[index];
  const next = [...current];
  next[index] = {
    ...incoming,
    status: incoming.fromMe
      ? advanceStatus(previous.status, incoming.status ?? "sent")
      : undefined,
  };
  return next;
}

function mergeMessages(
  history: ChatMessage[],
  current: ChatMessage[],
  conversationId: string,
): ChatMessage[] {
  const merged = [...history];
  const seen = new Map(history.map((item) => [item.id, item]));
  for (const item of current) {
    if (item.conversationId !== conversationId) {
      continue;
    }
    const existing = seen.get(item.id);
    if (!existing) {
      merged.push(item);
      seen.set(item.id, item);
      continue;
    }
    existing.status = existing.fromMe
      ? advanceStatus(existing.status, item.status ?? "sent")
      : undefined;
  }
  return merged;
}

export function AppShell() {
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [listReload, setListReload] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [messagesReload, setMessagesReload] = useState(0);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [groupInfoOpen, setGroupInfoOpen] = useState(false);
  const [railSection, setRailSection] = useState<RailSection>("chats");
  const [tabsVisible, setTabsVisible] = useState(true);
  const [sidebarView, setSidebarView] = useState<
    "list" | "new-chat" | "new-group" | "find-username" | "find-phone"
  >("list");
  const [moreOpen, setMoreOpen] = useState(false);
  const selectedIdRef = useRef(selectedId);
  const seenLiveIdsRef = useRef(new Set<string>());
  const markedReadRef = useRef(new Set<string>());
  const currentUserIdRef = useRef(user?.id);

  useEffect(() => {
    currentUserIdRef.current = user?.id;
  }, [user?.id]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    let cancelled = false;
    conversationsApi
      .list()
      .then((rows) => {
        if (!cancelled) {
          setConversations((previous) =>
            mergeConversationList(
              rows.map((row) => toConversation(row, user?.id)),
              previous,
            ),
          );
          setListError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setConversations([]);
          setListError(
            err instanceof Error ? err.message : "Could not load conversations",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setListLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id, listReload]);

  useEffect(() => {
    if (!selectedId || user?.id == null) {
      return;
    }
    const conversationId = Number(selectedId);
    if (!Number.isInteger(conversationId) || conversationId < 1) {
      return;
    }
    const currentUserId = user.id;
    let cancelled = false;
    messagesApi
      .list(conversationId)
      .then((payload) => {
        if (!cancelled) {
          const history = payload.messages.map((row) =>
            toChatMessage(row, currentUserId),
          );
          setMessages((current) => mergeMessages(history, current, String(conversationId)));
          setMessagesError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setMessages([]);
          setMessagesError(
            err instanceof Error ? err.message : "Could not load messages",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMessagesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, user?.id, messagesReload]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    const rows = term
      ? conversations.filter(
          (item) =>
            item.name.toLowerCase().includes(term) ||
            item.preview.toLowerCase().includes(term),
        )
      : conversations;
    return rows;
  }, [conversations, query]);

  const selected = conversations.find((item) => item.id === selectedId) ?? null;
  const thread = messages.filter((item) => item.conversationId === selectedId);
  const conversationIdsKey = conversations.map((item) => item.id).sort().join(",");
  const conversationIds = useMemo(
    () =>
      conversationIdsKey
        .split(",")
        .map((value) => Number(value))
        .filter((id) => Number.isInteger(id) && id > 0),
    [conversationIdsKey],
  );

  const { statuses: socketStatuses, sendClientEvent } = useConversationSockets(
    conversationIds,
    user?.id,
    (incoming) => {
      const isSelected = incoming.conversationId === selectedIdRef.current;
      const own = isOwnMessage(incoming.senderId, currentUserIdRef.current);
      if (isSelected) {
        setMessages((current) => upsertChatMessage(current, incoming));
      }
      const firstSeen = !seenLiveIdsRef.current.has(incoming.id);
      if (firstSeen) {
        seenLiveIdsRef.current.add(incoming.id);
      }
      setConversations((current) =>
        applyLiveConversation(
          current,
          incoming,
          selectedIdRef.current,
          own,
          firstSeen,
        ),
      );
    },
    (receipt) => {
      const selfId = user?.id;
      setMessages((current) =>
        current.map((item) => {
          if (item.id !== String(receipt.messageId) || !isOwnMessage(item.senderId, selfId)) {
            return item;
          }
          return { ...item, status: advanceStatus(item.status, receipt.status) };
        }),
      );
    },
    (event) => {
      if (event.userId !== 0 && event.userId === currentUserIdRef.current) {
        return;
      }
      setConversations((current) =>
        applyTypingState(current, event.conversationId, event.isTyping, event.userId),
      );
    },
    (event) => {
      if (event.userId === currentUserIdRef.current) {
        return;
      }
      setConversations((current) =>
        applyPresenceState(current, event.userId, event.isOnline, event.lastSeen),
      );
    },
    (event) => {
      if (event.action === "removed" && event.userId === currentUserIdRef.current) {
        if (selectedIdRef.current === event.conversationId) {
          selectedIdRef.current = null;
          setSelectedId(null);
          setMessages([]);
          setGroupInfoOpen(false);
        }
        setConversations((current) =>
          current.filter((item) => item.id !== event.conversationId),
        );
        return;
      }
      const numericId = Number(event.conversationId);
      if (!Number.isInteger(numericId) || numericId < 1) {
        return;
      }
      void conversationsApi
        .listMembers(numericId)
        .then((rows) => {
          setConversations((current) =>
            current.map((item) =>
              item.id === event.conversationId
                ? {
                    ...item,
                    memberCount: rows.length,
                    memberNames: Object.fromEntries(
                      rows.map((row) => [row.user_id, row.display_name]),
                    ),
                  }
                : item,
            ),
          );
        })
        .catch(() => undefined);
    },
  );

  const selectedNumericId = selected ? Number(selected.id) : null;
  const socketStatus =
    selectedNumericId != null ? socketStatuses[selectedNumericId] : undefined;

  const liveStatus =
    socketStatus === "connecting"
      ? "Connecting…"
      : socketStatus === "error"
        ? "Live connection failed"
        : socketStatus === "closed"
          ? "Live connection closed"
          : null;

  useEffect(() => {
    if (!selectedId || messagesLoading || user?.id == null) {
      return;
    }
    const conversationId = Number(selectedId);
    if (!Number.isInteger(conversationId) || conversationId < 1) {
      return;
    }
    for (const item of messages) {
      if (item.conversationId !== selectedId || isOwnMessage(item.senderId, user.id)) {
        continue;
      }
      const messageId = Number(item.id);
      if (!Number.isInteger(messageId) || messageId < 1) {
        continue;
      }
      const key = `${conversationId}:${messageId}`;
      if (markedReadRef.current.has(key)) {
        continue;
      }
      markedReadRef.current.add(key);
      const sent = sendClientEvent(conversationId, {
        type: "read",
        message_id: messageId,
      });
      if (!sent) {
        void messagesApi.markRead(conversationId, messageId).catch(() => {
          markedReadRef.current.delete(key);
        });
      }
    }
  }, [selectedId, messages, messagesLoading, user?.id, sendClientEvent]);

  function emitTyping(isTyping: boolean, conversationId = selectedIdRef.current) {
    if (!conversationId) {
      return;
    }
    const numericId = Number(conversationId);
    if (!Number.isInteger(numericId) || numericId < 1) {
      return;
    }
    sendClientEvent(numericId, { type: "typing", is_typing: isTyping });
  }

  async function sendMessage(content: string) {
    if (!selected || user?.id == null || sending) {
      return;
    }
    const conversationId = Number(selected.id);
    if (!Number.isInteger(conversationId) || conversationId < 1) {
      return;
    }
    emitTyping(false, selected.id);
    const currentUserId = user.id;
    const selectedConversationId = selected.id;
    setSending(true);
    setSendError(null);
    try {
      const row = await messagesApi.send(conversationId, content);
      const mapped = toChatMessage(row, currentUserId);
      seenLiveIdsRef.current.add(mapped.id);
      if (selectedIdRef.current !== selectedConversationId) {
        return;
      }
      setMessages((current) => upsertChatMessage(current, mapped));
      setConversations((current) => {
        const updated = current.map((item) =>
          item.id === selectedConversationId
            ? { ...item, preview: mapped.content, timestamp: mapped.timestamp }
            : item,
        );
        const active = updated.find((item) => item.id === selectedConversationId);
        const rest = updated.filter((item) => item.id !== selectedConversationId);
        return active ? [active, ...rest] : updated;
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not send message";
      setSendError(message);
      setNotice(message);
      throw err;
    } finally {
      setSending(false);
    }
  }

  function showPlaceholder(label: string) {
    const alreadyFramed = /coming soon/i.test(label);
    setNotice(alreadyFramed ? label : `${label} — Coming Soon`);
  }

  async function createGroup(name: string, memberIds: number[]) {
    if (user?.id == null) {
      throw new Error("Not signed in");
    }
    try {
      const row = await conversationsApi.createGroup(name, memberIds);
      const mapped = toConversation(row, user.id);
      setConversations((current) => [
        mapped,
        ...current.filter((item) => item.id !== mapped.id),
      ]);
      selectedIdRef.current = mapped.id;
      setSelectedId(mapped.id);
      setMessages([]);
      setMessagesError(null);
      setMessagesLoading(true);
      setSending(false);
      setSendError(null);
      setGroupInfoOpen(false);
      setSidebarView("list");
      setRailSection("chats");
      setNotice("Group created");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not create group";
      setNotice(message);
      throw err;
    }
  }

  async function openDirect(targetUserId: number) {
    if (user?.id == null) {
      throw new Error("Not signed in");
    }
    const row = await conversationsApi.createDirect(targetUserId);
    const mapped = toConversation(row, user.id);
    setConversations((current) => [
      mapped,
      ...current.filter((item) => item.id !== mapped.id),
    ]);
    selectedIdRef.current = mapped.id;
    setSelectedId(mapped.id);
    setMessages([]);
    setMessagesError(null);
    setMessagesLoading(true);
    setSending(false);
    setSendError(null);
    setGroupInfoOpen(false);
    setSidebarView("list");
    setRailSection("chats");
  }

  function selectConversation(id: string) {
    if (id !== selectedId) {
      emitTyping(false, selectedId);
      selectedIdRef.current = id;
      setSelectedId(id);
      setGroupInfoOpen(false);
      setMessages([]);
      setMessagesError(null);
      setMessagesLoading(true);
      setSending(false);
      setSendError(null);
    }
    setConversations((current) =>
      current.map((item) => (item.id === id ? { ...item, unread: 0 } : item)),
    );
  }

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-[var(--signal-bg)] text-[var(--signal-text)]">
      {tabsVisible ? (
        <div className="relative z-20 flex h-full shrink-0 overflow-visible">
          <NavRail
            section={railSection}
            onHideTabs={() => setTabsVisible(false)}
            onSection={(next) => {
              setRailSection(next);
              setSidebarView("list");
              setMoreOpen(false);
            }}
          />
        </div>
      ) : null}

      {railSection === "settings" ? (
        <SettingsDialog
          user={user}
          tabsVisible={tabsVisible}
          onShowTabs={() => setTabsVisible(true)}
          onHideTabs={() => setTabsVisible(false)}
          onClose={() => setRailSection("chats")}
          onLogout={() => {
            void logout().catch((err) => {
              const message = err instanceof Error ? err.message : "Could not log out";
              setNotice(message);
            });
          }}
        />
      ) : (
        <>
          <aside
            className={`flex min-h-0 w-full min-w-0 max-w-full shrink-0 flex-col overflow-x-hidden border-r border-[var(--signal-border)] bg-[var(--signal-panel)] md:w-[300px] md:max-w-[300px] ${
              selected && railSection === "chats" && sidebarView === "list"
                ? "hidden md:flex"
                : "flex"
            }`}
          >
            {railSection === "calls" ? (
              <div className="flex min-h-0 flex-1 flex-col">
                <header className="flex h-12 shrink-0 items-center gap-1 px-3">
                  <TabVisibilityControls
                    tabsVisible={tabsVisible}
                    onShow={() => setTabsVisible(true)}
                    onHide={() => setTabsVisible(false)}
                  />
                  {tabsVisible ? (
                    <h1 className="min-w-0 flex-1 text-[18px] font-semibold">Calls</h1>
                  ) : (
                    <span className="min-w-0 flex-1" />
                  )}
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="New call"
                    title="New call"
                    onClick={() => showPlaceholder("Calls")}
                  >
                    <Phone className="h-[18px] w-[18px]" />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="More"
                    title="More"
                    onClick={() => showPlaceholder("Call options")}
                  >
                    <MoreHorizontal className="h-[18px] w-[18px]" />
                  </button>
                </header>
                <ConversationSearch
                  value={query}
                  onChange={setQuery}
                  onFilter={() => showPlaceholder("Filter")}
                />
                <button
                  type="button"
                  onClick={() => showPlaceholder("Call links")}
                  className="mx-2 flex items-center gap-3 rounded-lg px-2 py-2 text-left text-[14px] hover:bg-[var(--signal-hover)]"
                >
                  Create a Call Link
                </button>
                <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                  <p className="text-[14px] font-semibold">No calls</p>
                  <p className="mt-1 text-[13px] text-[var(--signal-muted)]">
                    Recent calls will appear here.
                  </p>
                </div>
              </div>
            ) : railSection === "stories" ? (
              <div className="flex min-h-0 flex-1 flex-col">
                <header className="flex h-12 shrink-0 items-center gap-1 px-3">
                  <TabVisibilityControls
                    tabsVisible={tabsVisible}
                    onShow={() => setTabsVisible(true)}
                    onHide={() => setTabsVisible(false)}
                  />
                  {tabsVisible ? (
                    <h1 className="min-w-0 flex-1 text-[18px] font-semibold">Stories</h1>
                  ) : (
                    <span className="min-w-0 flex-1" />
                  )}
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Add story"
                    title="Add story"
                    onClick={() => showPlaceholder("Stories")}
                  >
                    <Plus className="h-[18px] w-[18px]" />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="More"
                    title="More"
                    onClick={() => showPlaceholder("Story options")}
                  >
                    <MoreHorizontal className="h-[18px] w-[18px]" />
                  </button>
                </header>
                <ConversationSearch
                  value={query}
                  onChange={setQuery}
                  onFilter={() => showPlaceholder("Filter")}
                />
                <button
                  type="button"
                  onClick={() => showPlaceholder("Stories")}
                  className="mx-2 flex items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-[var(--signal-hover)]"
                >
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[var(--signal-search)] text-[13px] font-medium">
                    {(user?.display_name.trim().slice(0, 1) || "Y").toUpperCase()}
                  </span>
                  <span>
                    <span className="block text-[14px]">My Story</span>
                    <span className="block text-[12px] text-[var(--signal-muted)]">Add a story</span>
                  </span>
                </button>
                <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                  <p className="text-[14px] font-semibold">No stories</p>
                  <p className="mt-1 text-[13px] text-[var(--signal-muted)]">
                    New updates will appear here.
                  </p>
                </div>
              </div>
            ) : sidebarView === "new-chat" ? (
              <NewChatPanel
                onBack={() => setSidebarView("list")}
                onNewGroup={() => setSidebarView("new-group")}
                onFindUsername={() => setSidebarView("find-username")}
                onFindPhone={() => setSidebarView("find-phone")}
                onPickUser={openDirect}
              />
            ) : sidebarView === "new-group" ? (
              <NewGroupDialog
                onClose={() => setSidebarView("new-chat")}
                onCreated={createGroup}
              />
            ) : sidebarView === "find-username" ? (
              <FindContactPanel
                mode="username"
                onBack={() => setSidebarView("new-chat")}
                onPickUser={openDirect}
              />
            ) : sidebarView === "find-phone" ? (
              <FindContactPanel
                mode="phone"
                onBack={() => setSidebarView("new-chat")}
                onPickUser={openDirect}
              />
            ) : (
              <>
                <header className="relative flex h-12 shrink-0 items-center gap-1 px-3">
                  <TabVisibilityControls
                    tabsVisible={tabsVisible}
                    onShow={() => setTabsVisible(true)}
                    onHide={() => setTabsVisible(false)}
                  />
                  {tabsVisible ? (
                    <h1 className="min-w-0 flex-1 text-[18px] font-semibold">Chats</h1>
                  ) : (
                    <span className="min-w-0 flex-1" />
                  )}
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="New chat"
                    title="New chat"
                    onClick={() => setSidebarView("new-chat")}
                  >
                    <SquarePen className="h-[18px] w-[18px]" />
                  </button>
                  <div className="relative">
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label="More"
                      title="More"
                      onClick={() => setMoreOpen((open) => !open)}
                    >
                      <MoreHorizontal className="h-[18px] w-[18px]" />
                    </button>
                    {moreOpen ? (
                      <div
                        role="menu"
                        className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-lg border border-[var(--signal-border)] bg-[var(--signal-panel)] py-1 shadow-sm"
                      >
                        {["View Archive", "Add chat folder", "Notification profile"].map(
                          (item) => (
                            <button
                              key={item}
                              type="button"
                              role="menuitem"
                              onClick={() => {
                                setMoreOpen(false);
                                showPlaceholder(item);
                              }}
                              className="flex w-full px-3 py-2 text-left text-sm hover:bg-[var(--signal-hover)]"
                            >
                              {item}
                            </button>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                </header>
                <ConversationSearch
                  value={query}
                  onChange={setQuery}
                  onFilter={() => showPlaceholder("Filter")}
                />
                <ConversationList
                  conversations={filtered}
                  selectedId={selectedId}
                  onSelect={selectConversation}
                  loading={listLoading}
                  error={listError}
                  onRetry={() => {
                    setListLoading(true);
                    setListReload((value) => value + 1);
                  }}
                  emptyMessage={query.trim() ? "No conversations found" : "No chats"}
                />
              </>
            )}
          </aside>

          {selected && user && railSection === "chats" && sidebarView === "list" ? (
            <ChatPane
              conversation={selected}
              messages={thread}
              currentUserId={user.id}
              onSend={sendMessage}
              onTypingChange={emitTyping}
              typingLabel={typingLabelFor(selected)}
              onBack={() => {
                emitTyping(false, selected.id);
                selectedIdRef.current = null;
                setSelectedId(null);
                setGroupInfoOpen(false);
                setMessages([]);
                setMessagesError(null);
                setMessagesLoading(false);
                setSending(false);
                setSendError(null);
              }}
              onPlaceholder={showPlaceholder}
              onGroupInfo={
                selected.kind === "group" ? () => setGroupInfoOpen(true) : undefined
              }
              loading={messagesLoading}
              error={messagesError}
              sending={sending}
              sendError={sendError}
              liveStatus={liveStatus}
              onRetry={() => {
                setMessages([]);
                setMessagesError(null);
                setMessagesLoading(true);
                setMessagesReload((value) => value + 1);
              }}
            />
          ) : railSection === "calls" ? (
            <SectionEmptyPane
              icon={<Phone className="h-14 w-14" strokeWidth={1.25} />}
              message={
                <>
                  Click{" "}
                  <Phone className="mb-0.5 inline h-3.5 w-3.5 align-text-bottom" strokeWidth={1.75} />{" "}
                  to start a new voice or video call.
                </>
              }
            />
          ) : railSection === "stories" ? (
            <SectionEmptyPane
              icon={<Copy className="h-14 w-14" strokeWidth={1.25} />}
              message="Click to view a story"
            />
          ) : (
            <WelcomePane onPlaceholder={showPlaceholder} />
          )}
        </>
      )}

      {groupInfoOpen && selected && user && selected.kind === "group" ? (
        <GroupInfoDialog
          conversation={selected}
          currentUserId={user.id}
          onClose={() => setGroupInfoOpen(false)}
          onMemberCountChange={(count) => {
            setConversations((current) =>
              current.map((item) =>
                item.id === selected.id ? { ...item, memberCount: count } : item,
              ),
            );
          }}
          onLeftGroup={() => {
            const id = selected.id;
            selectedIdRef.current = null;
            setSelectedId(null);
            setMessages([]);
            setGroupInfoOpen(false);
            setConversations((current) => current.filter((item) => item.id !== id));
          }}
          onToast={setNotice}
        />
      ) : null}
      {notice ? (
        <Toast message={notice} onDismiss={() => setNotice(null)} />
      ) : null}
    </div>
  );
}
