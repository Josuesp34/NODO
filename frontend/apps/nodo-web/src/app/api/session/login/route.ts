import { establishSession } from "@/lib/session-server";

export async function POST(request: Request) {
  return establishSession("auth/login", await request.json());
}
