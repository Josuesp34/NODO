import { establishSession } from "@/lib/session-server";
import { protectSessionJson } from "@/lib/bff-security";

export const POST = protectSessionJson((body) => establishSession("auth/athletes/activate", body));
