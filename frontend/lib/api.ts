"use client";

const API_BASE =
  (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

function wsBaseFromApi(apiBase: string): string {
  if (apiBase.startsWith("https://")) {
    return `wss://${apiBase.slice("https://".length)}`;
  }
  if (apiBase.startsWith("http://")) {
    return `ws://${apiBase.slice("http://".length)}`;
  }
  return "ws://127.0.0.1:8000";
}

export const WS_BASE = (
  process.env.NEXT_PUBLIC_WS_BASE ?? wsBaseFromApi(API_BASE)
).replace(/\/$/, "");

function browserFetch(input: string, init: RequestInit): Promise<Response> {
  // Next.js patches the module-level `fetch` during App Router prerender and can
  // return a promise that never settles. window.fetch is the real browser call.
  return window.fetch(input, init);
}

export type AuthUser = {
  id: number;
  username: string | null;
  phone: string | null;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  is_online: boolean;
  last_seen: string | null;
  created_at: string;
};

export type LoginPayload = {
  username?: string | null;
  phone?: string | null;
  otp: string;
};

export type RegisterPayload = {
  username?: string | null;
  phone?: string | null;
  display_name: string;
  avatar_url?: string | null;
  otp: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

async function readError(response: Response): Promise<string> {
  const data: unknown = await response.json().catch(() => null);
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
      const first = detail[0] as { msg?: string };
      if (typeof first.msg === "string") {
        return first.msg.replace(/^Value error,\s*/i, "");
      }
    }
  }
  return `Request failed (${response.status})`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await browserFetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function splitIdentifier(identifier: string): {
  username?: string;
  phone?: string;
} {
  const value = identifier.trim();
  if (!value) {
    return {};
  }
  if (value.startsWith("+") || /^\d[\d\s-]*$/.test(value)) {
    return { phone: value.replace(/\s/g, "") };
  }
  return { username: value };
}

export type PublicUser = {
  id: number;
  username: string | null;
  phone: string | null;
  display_name: string;
  avatar_url: string | null;
  is_online: boolean;
  last_seen: string | null;
};

export type ConversationMember = {
  user_id: number;
  role: string;
  joined_at: string;
  last_read_at: string | null;
  user: PublicUser;
};

export type ConversationOut = {
  id: number;
  type: string;
  name: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  members: ConversationMember[];
  other_user: PublicUser | null;
};

export type ContactOut = {
  id: number;
  created_at: string;
  user: PublicUser;
};

export type GroupMemberOut = {
  user_id: number;
  username: string | null;
  display_name: string;
  avatar_url: string | null;
  role: string;
  joined_at: string;
  is_online: boolean;
  last_seen: string | null;
};

export const authApi = {
  me: () => request<AuthUser>("/auth/me"),
  login: (payload: LoginPayload) =>
    request<AuthUser>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  register: (payload: RegisterPayload) =>
    request<AuthUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () =>
    request<{ message: string }>("/auth/logout", {
      method: "POST",
    }),
};

export const conversationsApi = {
  list: () => request<ConversationOut[]>("/conversations"),
  createGroup: (name: string, memberIds: number[]) =>
    request<ConversationOut>("/conversations/group", {
      method: "POST",
      body: JSON.stringify({ name, member_ids: memberIds }),
    }),
  createDirect: (targetUserId: number) =>
    request<ConversationOut>("/conversations/direct", {
      method: "POST",
      body: JSON.stringify({ target_user_id: targetUserId }),
    }),
  listMembers: (conversationId: number) =>
    request<GroupMemberOut[]>(`/conversations/${conversationId}/members`),
  addMember: (conversationId: number, userId: number) =>
    request<GroupMemberOut>(`/conversations/${conversationId}/members`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  removeMember: (conversationId: number, userId: number) =>
    request<void>(`/conversations/${conversationId}/members/${userId}`, {
      method: "DELETE",
    }),
};

export const contactsApi = {
  list: () => request<ContactOut[]>("/contacts"),
  search: (query: string) =>
    request<PublicUser[]>(`/contacts/search?q=${encodeURIComponent(query)}`),
};

export type MessageReceiptOut = {
  user_id: number;
  status: string;
  delivered_at: string | null;
  read_at: string | null;
};

export type MessageOut = {
  id: number;
  conversation_id: number;
  sender_id: number;
  content: string;
  created_at: string;
  updated_at: string;
  status: string;
  sender: PublicUser | null;
  receipts: MessageReceiptOut[];
};

export type MessageListOut = {
  messages: MessageOut[];
  limit: number;
  offset: number;
  total: number;
};

export const messagesApi = {
  list: (conversationId: number) =>
    request<MessageListOut>(
      `/conversations/${conversationId}/messages?limit=100&offset=0`,
    ),
  send: (conversationId: number, content: string) =>
    request<MessageOut>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  markRead: (conversationId: number, messageId: number) =>
    request<MessageReceiptOut>(
      `/conversations/${conversationId}/messages/${messageId}/read`,
      { method: "POST" },
    ),
};
