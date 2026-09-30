import { currentIdentity } from "@/lib/session-server";

export async function GET() {
  return currentIdentity();
}
