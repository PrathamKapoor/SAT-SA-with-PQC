import { type NextRequest, NextResponse } from "next/server";
import { ORG_COOKIE, SESSION_COOKIE } from "@/lib/api/client";

/**
 * Clears the local session after the backend reported it invalid (expired or
 * revoked). It does not call the backend: the session is already unusable.
 * Deliberate sign-out uses the signOut server action, which revokes it.
 */
export function GET(request: NextRequest) {
  const reason = request.nextUrl.searchParams.get("reason") === "expired" ? "expired" : "signed-out";
  const response = NextResponse.redirect(new URL(`/login?reason=${reason}`, request.url));
  response.cookies.delete(SESSION_COOKIE);
  response.cookies.delete(ORG_COOKIE);
  return response;
}
