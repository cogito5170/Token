import type { Schemas } from "../../../lib/api";

/** The audit log is admin-only (API contract); other roles get no screen content and no request. */
export const canViewAudit = (role: Schemas["Workspace"]["role"] | null | undefined) => role === "admin";
