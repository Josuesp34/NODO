import { logoutSession } from "@/lib/session-server";
import { protectSessionRequest } from "@/lib/bff-security";

export const POST = protectSessionRequest(logoutSession);
