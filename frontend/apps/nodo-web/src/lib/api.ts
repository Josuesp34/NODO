import type { ApiProblem } from "./contracts";
import { clearOfflineData } from "./offline-store";

export class NodoWebError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "NodoWebError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

export async function nodoRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const requestBody: BodyInit | undefined = options.body === undefined
    ? undefined
    : options.body instanceof FormData
      ? options.body
      : JSON.stringify(options.body);
  const response = await fetch(`/api/nodo/${path.replace(/^\//, "")}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(isFormData || options.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
    body: requestBody,
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) clearOfflineData();
    const payload = (await response.json().catch(() => null)) as { detail?: unknown; message?: string } | null;
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : payload?.message ?? `NODO respondió ${response.status}`;
    throw new NodoWebError(response.status, message, payload?.detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function problemFrom(error: unknown): ApiProblem {
  if (error instanceof NodoWebError) {
    return { status: error.status, message: error.message, detail: error.detail };
  }
  return { status: 0, message: "No fue posible conectar con NODO." };
}

export function isContractUnavailable(error: unknown) {
  return error instanceof NodoWebError && [404, 405, 501].includes(error.status);
}
