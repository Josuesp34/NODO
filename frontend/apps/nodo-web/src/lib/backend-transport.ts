export type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
};

type BackendFetch = (path: string, init?: RequestInit) => Promise<Response>;

// Cloud Run IAM authenticates the service; Authorization remains the NODO user session.
export function createBackendFetch(apiUrl: string, audience = "", fetcher: typeof fetch = fetch): BackendFetch {
  const baseUrl = apiUrl.replace(/\/$/, "");
  let cachedIdentity: { token: string; expiresAt: number } | undefined;
  let pendingIdentity: Promise<string> | undefined;

  async function serviceIdentity(): Promise<string> {
    if (cachedIdentity && cachedIdentity.expiresAt > Date.now() + 60_000) return cachedIdentity.token;
    if (pendingIdentity) return pendingIdentity;
    pendingIdentity = (async () => {
      const metadata = new URL("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity");
      metadata.searchParams.set("audience", audience);
      metadata.searchParams.set("format", "full");
      const response = await fetcher(metadata, {
        headers: { "Metadata-Flavor": "Google" },
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      });
      if (!response.ok) throw new Error("No se pudo obtener la identidad de Cloud Run.");
      const token = (await response.text()).trim();
      let expiresAt: number;
      try {
        const claims = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString("utf8"));
        expiresAt = Number(claims.exp) * 1_000;
      } catch {
        throw new Error("La identidad de Cloud Run no es válida.");
      }
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
        throw new Error("La identidad de Cloud Run expiró.");
      }
      cachedIdentity = { token, expiresAt };
      return token;
    })();
    try {
      return await pendingIdentity;
    } finally {
      pendingIdentity = undefined;
    }
  }

  return async (path, init = {}) => {
    const headers = new Headers(init.headers);
    if (audience) headers.set("X-Serverless-Authorization", `Bearer ${await serviceIdentity()}`);
    return fetcher(`${baseUrl}/${path.replace(/^\//, "")}`, { ...init, headers, cache: "no-store" });
  };
}

export async function fetchWithRotatingSession(
  path: string,
  init: RequestInit,
  session: { access?: string; refresh?: string },
  backendFetch: BackendFetch,
): Promise<{ response: Response; rotated?: TokenPair }> {
  const authorized = (access: string) => {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${access}`);
    return backendFetch(path, { ...init, headers });
  };
  if (session.access) {
    const response = await authorized(session.access);
    if (response.status !== 401) return { response };
  }
  const unauthorized = () => ({ response: Response.json({ detail: "La sesión expiró." }, { status: 401 }) });
  if (!session.refresh) return unauthorized();
  const refreshResponse = await backendFetch("auth/refresh", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: session.refresh }),
  });
  if (!refreshResponse.ok) return unauthorized();
  const rotated = (await refreshResponse.json()) as TokenPair;
  return { response: await authorized(rotated.access_token), rotated };
}
