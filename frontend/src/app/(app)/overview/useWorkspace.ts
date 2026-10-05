"use client";
import { useEffect, useState } from "react";
import { getWorkspaceId } from "../../../lib/auth/session";

/** Active workspace id as chosen by the shell switcher; null until it is known. */
export function useWorkspaceId(): string | null {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    const read = () => { const v = getWorkspaceId(); if (v) setId((p) => (p === v ? p : v)); };
    read();
    const t = setInterval(read, 300);
    return () => clearInterval(t);
  }, []);
  return id;
}
