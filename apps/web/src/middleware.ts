import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC = ["/login", "/register", "/forgot", "/reset"];

export function middleware(request: NextRequest) {
  const access = request.cookies.get("hc_access")?.value;
  const refresh = request.cookies.get("hc_refresh")?.value;
  const token = access || refresh;
  const path = request.nextUrl.pathname;
  const isPublic = PUBLIC.some((p) => path.startsWith(p));
  if (!token && !isPublic) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (token && isPublic) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api|media).*)"],
};
