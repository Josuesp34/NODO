import { backendFetch, passThrough } from "@/lib/session-server";
import { protectSessionJson } from "@/lib/bff-security";

export const POST = protectSessionJson(async (body) => {
  const response = await backendFetch("auth/password-reset/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return passThrough(response);
});
