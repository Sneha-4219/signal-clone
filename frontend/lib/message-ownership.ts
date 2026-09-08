/**
 * Single ownership rule for 1-to-1 chat:
 * a message is own iff its backend sender_id matches the authenticated user id.
 * Receipts, names, member order, and send path must not decide this.
 */

export function normalizeUserId(value: unknown): number | null {
  if (typeof value === "number") {
    if (!Number.isInteger(value) || value < 1) {
      return null;
    }
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!/^[0-9]+$/.test(trimmed)) {
      return null;
    }
    const parsed = Number.parseInt(trimmed, 10);
    if (!Number.isInteger(parsed) || parsed < 1) {
      return null;
    }
    return parsed;
  }
  return null;
}

export function readMessageSenderId(row: {
  sender_id?: unknown;
  senderId?: unknown;
  sender?: { id?: unknown } | null;
}): number | null {
  const fromSenderId = normalizeUserId(row.sender_id);
  if (fromSenderId != null) {
    return fromSenderId;
  }
  const fromCamel = normalizeUserId(row.senderId);
  if (fromCamel != null) {
    return fromCamel;
  }
  return normalizeUserId(row.sender?.id);
}

export function isOwnMessage(
  senderId: unknown,
  currentUserId: unknown,
): boolean {
  const sender = normalizeUserId(senderId);
  const self = normalizeUserId(currentUserId);
  return sender != null && self != null && sender === self;
}
