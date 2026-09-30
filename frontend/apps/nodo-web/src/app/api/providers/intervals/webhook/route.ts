import { backendFetch, passThrough } from "@/lib/session-server";
import { NextResponse } from "next/server";
// Public provider ingress; API stays IAM-private. Authentication is the provider's body.secret.
export async function POST(request: Request) {
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = []; let length = 0;
  const declared = request.headers.get("content-length");
  if (declared && (!/^\d+$/.test(declared) || Number(declared) > 1024 * 1024)) return NextResponse.json({ detail: "Webhook demasiado grande" }, { status: 413 });
  if (reader) while (true) {
    const next = await reader.read(); if (next.done) break;
    length += next.value.byteLength;
    if (length > 1024 * 1024) { await reader.cancel(); return NextResponse.json({ detail: "Webhook demasiado grande" }, { status: 413 }); }
    chunks.push(next.value);
  }
  const body = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return passThrough(await backendFetch("connections/intervals/webhook", { method: "POST", headers: { "Content-Type": "application/json" }, body }));
}
