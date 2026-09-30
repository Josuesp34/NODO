type JsonHandler = (body: unknown) => Promise<Response>;
type ProxyHandler = (path: string, init: RequestInit) => Promise<Response>;

const sessionDefaultBytes = 16 * 1024;
const jsonDefaultBytes = 1024 * 1024;
const fitDefaultBytes = 10 * 1024 * 1024;
const multipartOverheadBytes = 64 * 1024;

class RequestRejected extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function configuredLimit(name: string, fallback: number): number {
  const value = process.env[name];
  if (value === undefined) return fallback;
  const limit = /^\d+$/.test(value) ? Number(value) : NaN;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 0x7fffffff - multipartOverheadBytes) {
    throw new RequestRejected(503, "La protección de solicitudes no está configurada.");
  }
  return limit;
}

function requireSameOrigin(request: Request) {
  if (["GET", "HEAD", "OPTIONS"].includes(request.method)) return;
  const configuredOrigin = process.env.NODO_APP_ORIGIN;
  let expectedOrigin: string;
  try {
    const target = new URL(configuredOrigin ?? request.url);
    if (!["http:", "https:"].includes(target.protocol) || target.username || target.password
      || (configuredOrigin !== undefined && (target.pathname !== "/" || target.search || target.hash))) {
      throw new Error("Invalid origin");
    }
    expectedOrigin = target.origin;
  } catch {
    throw new RequestRejected(503, "La protección de solicitudes no está configurada.");
  }
  // Origin is required even when Fetch Metadata is absent; SameSite alone does not prevent CSRF.
  if (request.headers.get("origin") !== expectedOrigin
    || ["cross-site", "same-site"].includes(request.headers.get("sec-fetch-site") ?? "")) {
    throw new RequestRejected(403, "El origen de la solicitud no está autorizado.");
  }
}

async function readBody(request: Request, maxBytes: number): Promise<ArrayBuffer> {
  const lengthHeader = request.headers.get("content-length");
  if (lengthHeader !== null) {
    if (!/^\d+$/.test(lengthHeader)) throw new RequestRejected(400, "El tamaño de la solicitud no es válido.");
    if (Number(lengthHeader) > maxBytes) {
      void request.body?.cancel().catch(() => undefined);
      throw new RequestRejected(413, "La solicitud supera el tamaño permitido.");
    }
  }
  if (!request.body) {
    if (lengthHeader !== null && Number(lengthHeader) !== 0) {
      throw new RequestRejected(400, "El tamaño de la solicitud no coincide con el cuerpo recibido.");
    }
    return new ArrayBuffer(0);
  }
  const reader = request.body.getReader();
  let bytes = new Uint8Array(Math.min(8192, maxBytes));
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        // Do not await cancellation: a hostile stream may never resolve its cancel promise.
        void reader.cancel().catch(() => undefined);
        throw new RequestRejected(413, "La solicitud supera el tamaño permitido.");
      }
      if (size > bytes.byteLength) {
        const expanded = new Uint8Array(Math.min(maxBytes, Math.max(size, bytes.byteLength * 2)));
        expanded.set(bytes);
        bytes = expanded;
      }
      bytes.set(value, size - value.byteLength);
    }
  } finally {
    reader.releaseLock();
  }
  if (lengthHeader !== null && Number(lengthHeader) !== size) {
    throw new RequestRejected(400, "El tamaño de la solicitud no coincide con el cuerpo recibido.");
  }
  return bytes.buffer.slice(0, size);
}

async function protect(request: Request, handler: () => Promise<Response>): Promise<Response> {
  try {
    requireSameOrigin(request);
    return await handler();
  } catch (error) {
    if (!(error instanceof RequestRejected)) throw error;
    return Response.json({ detail: error.message }, {
      status: error.status,
      headers: { "Cache-Control": "no-store" },
    });
  }
}

export function protectSessionJson(handler: JsonHandler) {
  return (request: Request): Promise<Response> => protect(request, async () => {
    const bytes = await readBody(request, configuredLimit("NODO_BFF_SESSION_MAX_BYTES", sessionDefaultBytes));
    let body: unknown;
    try {
      body = JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      throw new RequestRejected(400, "El cuerpo de la solicitud debe ser JSON válido.");
    }
    return handler(body);
  });
}

export function protectSessionRequest(handler: () => Promise<Response>) {
  return (request: Request): Promise<Response> => protect(request, async () => {
    await readBody(request, configuredLimit("NODO_BFF_SESSION_MAX_BYTES", sessionDefaultBytes));
    return handler();
  });
}

export function protectProxyRequest(handler: ProxyHandler) {
  return (path: string, request: Request): Promise<Response> => protect(request, async () => {
    const headers = new Headers({ Accept: request.headers.get("accept") ?? "application/json" });
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("Content-Type", contentType);
    const hasBody = !["GET", "HEAD"].includes(request.method);
    let body: ArrayBuffer | undefined;
    if (hasBody) {
      // Keep the backend's 10 MiB FIT file limit plus bounded multipart framing, not 10 MiB of JSON.
      const isFit = /^athletes\/\d+\/activities\/fit(?:\?|$)/.test(path)
        && /^multipart\/form-data(?:;|$)/i.test(contentType ?? "");
      const limit = isFit
        ? configuredLimit("NODO_BFF_FIT_MAX_BYTES", fitDefaultBytes) + multipartOverheadBytes
        : configuredLimit("NODO_BFF_JSON_MAX_BYTES", jsonDefaultBytes);
      body = await readBody(request, limit);
    }
    return handler(path, { method: request.method, headers, body, redirect: "manual" });
  });
}
