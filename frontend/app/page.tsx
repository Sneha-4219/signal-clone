"use client";

import { AuthProvider, useAuth } from "@/components/auth/AuthProvider";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { AppShell } from "@/components/shell/AppShell";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

function SessionGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center bg-[var(--signal-chat)] text-sm text-[var(--signal-muted)]">
        Checking session…
      </div>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  return <AppShell />;
}

export default function Home() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <SessionGate />
      </AuthProvider>
    </ThemeProvider>
  );
}
