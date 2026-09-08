type AvatarProps = {
  initials: string;
  accent: string;
  size?: "sm" | "md" | "lg";
  online?: boolean;
  src?: string | null;
};

const sizes = {
  sm: "h-9 w-9 text-xs",
  md: "h-11 w-11 text-sm",
  lg: "h-12 w-12 text-sm",
};

export function Avatar({ initials, accent, size = "md", online, src }: AvatarProps) {
  return (
    <span className="relative inline-flex shrink-0">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          className={`${sizes[size]} rounded-full object-cover`}
        />
      ) : (
        <span
          className={`inline-flex items-center justify-center rounded-full font-semibold text-white ${sizes[size]}`}
          style={{ backgroundColor: accent }}
          aria-hidden
        >
          {initials}
        </span>
      )}
      {online ? (
        <span className="absolute right-0 bottom-0 h-2.5 w-2.5 rounded-full border-2 border-[var(--signal-panel)] bg-emerald-500" />
      ) : null}
    </span>
  );
}
