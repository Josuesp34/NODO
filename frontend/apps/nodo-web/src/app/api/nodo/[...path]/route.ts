import { authenticatedProxy } from "@/lib/session-server";
import { NextResponse } from "next/server";

const blocked = new Set(["auth/login", "auth/refresh", "auth/coaches", "auth/superusers"]);

async function forward(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const pathname = path.join("/");
  if (blocked.has(pathname)) {
    return NextResponse.json({ detail: "Este contrato no se expone al navegador." }, { status: 404 });
  }
  const query = new URL(request.url).search;
  return authenticatedProxy(`${pathname}${query}`, request);
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
