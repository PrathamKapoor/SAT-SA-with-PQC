import type { ErrorDetail } from "./types";

/**
 * A failed API call, as the backend's error envelope describes it
 * (docs/API_CONTRACT.md, section 9). `status` 0 and code NETWORK_ERROR mean
 * the SAT-SA service could not be reached at all.
 */
export interface ApiErrorInfo {
  status: number;
  code: string;
  message: string;
  requestId: string;
  details: ErrorDetail[];
}

export class ApiError extends Error {
  constructor(readonly info: ApiErrorInfo) {
    super(`SAT-SA API ${info.status} ${info.code}`);
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** How the UI presents an error: what failed, whether retrying can help. */
export interface ErrorPresentation {
  title: string;
  message: string;
  retry: boolean;
}

export function present(info: ApiErrorInfo): ErrorPresentation {
  switch (info.code) {
    case "NETWORK_ERROR":
      return { title: "The SAT-SA service could not be reached", message: "Check that the backend is running, then try again.", retry: true };
    case "ORGANIZATION_REQUIRED":
      return { title: "No organization selected", message: "Select the organization to work in.", retry: false };
    case "AUTHENTICATION_ERROR":
      return { title: "Your session has ended", message: "Sign in again to continue.", retry: false };
    case "ORIGIN_DENIED":
      return { title: "This site is not allowed to sign in", message: "The SAT-SA service does not accept sign-in from this origin. An administrator must add it to SATSA_ALLOWED_ORIGINS.", retry: false };
    case "PERMISSION_DENIED":
      return { title: "Not permitted", message: "Your role in this organization does not allow this, or the record belongs to another organization.", retry: false };
    case "NOT_FOUND":
      return { title: "Not found", message: "The record does not exist or has not been produced yet.", retry: false };
    case "DOMAIN_CONFLICT":
    case "DUPLICATE_ENTRY":
    case "IDENTITY_EXISTS":
      return { title: "Conflict", message: info.message, retry: false };
    case "DOMAIN_INVALID":
      return { title: "Not possible in the current state", message: info.message, retry: false };
    case "VALIDATION_ERROR":
      return { title: "The request was not valid", message: fieldMessages(info) || info.message, retry: false };
    case "REQUEST_TOO_LARGE":
      return { title: "File too large", message: "The upload exceeds the size the SAT-SA service accepts.", retry: false };
    case "RATE_LIMITED":
      return { title: "Too many requests", message: "Wait a moment and try again.", retry: true };
    case "NOT_READY":
      return { title: "The SAT-SA service is not ready", message: "A backend dependency is unavailable. Try again shortly.", retry: true };
    default:
      return info.status >= 500
        ? { title: "The SAT-SA service failed", message: "An unexpected backend error occurred.", retry: true }
        : { title: "The request failed", message: info.message || `HTTP ${info.status}`, retry: false };
  }
}

function fieldMessages(info: ApiErrorInfo): string {
  return info.details
    .map((d) => {
      const where = (d.location ?? []).filter((p) => p !== "body" && p !== "query" && p !== "header").join(".");
      return d.message ? (where ? `${where}: ${d.message}` : d.message) : "";
    })
    .filter(Boolean)
    .join("; ");
}

/** Result type for server actions called from client components. */
export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: ApiErrorInfo };
