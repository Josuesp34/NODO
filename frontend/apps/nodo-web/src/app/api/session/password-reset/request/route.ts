import { backendFetch, passThrough } from "@/lib/session-server";

export async function POST(request: Request) {
  const response = await backendFetch("auth/password-reset/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  return passThrough(response);
}
