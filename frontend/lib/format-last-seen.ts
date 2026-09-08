export function formatLastSeen(iso: string | null | undefined): string {
  if (!iso) {
    return "offline";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "offline";
  }
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) {
    return "last seen just now";
  }
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin === 1) {
    return "last seen 1 minute ago";
  }
  if (diffMin < 60) {
    return `last seen ${diffMin} minutes ago`;
  }
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    const hours = Math.floor(diffMin / 60);
    if (hours === 1) {
      return "last seen 1 hour ago";
    }
    return `last seen ${hours} hours ago`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return "last seen yesterday";
  }
  return `last seen ${date.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}
