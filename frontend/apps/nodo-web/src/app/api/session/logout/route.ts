import { logoutSession } from "@/lib/session-server";

export async function POST() {
  return logoutSession();
}
