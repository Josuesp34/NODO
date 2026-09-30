"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { clearOfflineData, observeOfflineInvalidation } from "@/lib/offline-store";
import { capabilitiesFor, type Capability, type Identity } from "@/lib/contracts";
import { Brand, LoadingState } from "./ui";
import { OfflineWorkspace } from "./offline-workspace";

type SessionState = { identity: Identity; capabilities: Capability[] };
const SessionContext = createContext<SessionState | null>(null);

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession debe usarse dentro de ProductShell");
  return value;
}

const coachLinks = [
  ["/coach", "01", "Resumen"],
  ["/coach/athletes", "02", "Atletas"],
  ["/coach/review", "03", "Revisión"],
  ["/coach/copilot", "04", "Copiloto"],
  ["/coach/recommendations", "05", "Propuestas"],
  ["/coach/groups", "06", "Grupos"],
  ["/coach/templates", "07", "Plantillas"],
] as const;

const athleteLinks = [
  ["/athlete/today", "01", "Hoy"],
  ["/athlete/week", "02", "Semana"],
  ["/athlete/check-in", "03", "Check-in"],
  ["/athlete/complaints", "04", "Molestias"],
  ["/athlete/connections", "05", "Conexiones"],
  ["/athlete/profile", "06", "Perfil"],
  ["/athlete/activities", "07", "Actividades"],
  ["/athlete/assistant", "08", "Asistente"],
] as const;

const staffLinks = [["/admin/operations", "01", "Operación"], ["/settings/commercial", "02", "Administración"]] as const;

export function ProductShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<SessionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [validation, setValidation] = useState(0);

  useEffect(() => {
    const revalidate = () => { setSession(null); setValidation((value) => value + 1); };
    const disconnected = () => { setSession(null); setOffline(true); };
    const unsubscribe = observeOfflineInvalidation(revalidate);
    window.addEventListener("offline", disconnected); window.addEventListener("online", revalidate);
    return () => { unsubscribe(); window.removeEventListener("offline", disconnected); window.removeEventListener("online", revalidate); };
  }, []);

  useEffect(() => {
    setError(null); setOffline(false);
    const controller = new AbortController();
    void fetch("/api/session/me", { cache: "no-store", signal: controller.signal }).then(async (response) => {
      if (controller.signal.aborted) return;
      if (response.status === 401) {
        clearOfflineData();
        router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        return;
      }
      if (response.status === 403) { clearOfflineData(); setSession(null); throw new Error("Esta cuenta no tiene acceso activo."); }
      if (!response.ok) throw new Error("No pudimos validar tu sesión.");
      const identity = await response.json() as Identity;
      if (!controller.signal.aborted) setSession({ identity, capabilities: capabilitiesFor(identity) });
    }).catch((reason: unknown) => {
      if (controller.signal.aborted) return;
      if (!navigator.onLine || reason instanceof TypeError) setOffline(true);
      else setError(reason instanceof Error ? reason.message : "No pudimos validar tu sesión.");
    });
    return () => controller.abort();
  }, [pathname, router, validation]);

  const requested: Capability | null = pathname.startsWith("/admin") ? "staff" : pathname.startsWith("/coach") ? "coach" : pathname.startsWith("/athlete") ? "athlete" : null;
  const links = requested === "staff" || (!requested && session?.capabilities.includes("staff")) ? staffLinks : requested === "coach" ? coachLinks : athleteLinks;
  const mobileLinks = links.slice(0, 4);
  const context = useMemo(() => session, [session]);

  async function logout() {
    clearOfflineData();
    await fetch("/api/session/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/");
    router.refresh();
  }

  if (offline) return <main id="contenido"><OfflineWorkspace /></main>;
  if (error) return <main className="loading-screen" role="alert">{error}</main>;
  if (!session || !context) return <LoadingState />;
  if (requested && !session.capabilities.includes(requested) && !session.capabilities.includes("staff")) {
    const fallback = session.capabilities.includes("coach") ? "/coach" : "/athlete/today";
    return <main className="loading-screen"><div><p>Esta cuenta no tiene acceso a este módulo.</p><Link className="button" href={fallback}>Abrir módulo disponible</Link></div></main>;
  }

  return (
    <SessionContext.Provider value={context}>
      <div className="product-layout">
        <header className="product-header">
          <Brand lab={requested === "coach"} />
          <div className="header-actions">
            {session.capabilities.includes("coach") && session.capabilities.includes("athlete") ? (
              <nav className="capability-switcher" aria-label="Cambiar módulo">
                <Link href="/athlete/today" aria-current={requested === "athlete" ? "page" : undefined}>Atleta</Link>
                <Link href="/coach" aria-current={requested === "coach" ? "page" : undefined}>Coach</Link>
              </nav>
            ) : null}
            <span className="header-user muted">{session.identity.first_name}</span>
            <button className="button button-quiet" type="button" onClick={logout}>Salir</button>
          </div>
        </header>
        <div className="product-grid">
          <aside className="side-nav">
            <p className="nav-label">{requested === "staff" ? "Operación NODO" : requested === "coach" ? "NODO Lab" : "Mi NODO"}</p>
            <nav className="nav-links" aria-label="Navegación principal">
              {links.map(([href, index, label]) => <Link className="nav-link" data-active={pathname === href || (href !== "/coach" && pathname.startsWith(`${href}/`))} href={href} key={href}><span>{index}</span>{label}</Link>)}
            </nav>
            <div className="side-account"><Link className="nav-link" data-active={pathname.startsWith("/settings")} href="/settings/account"><span>⚙</span>Ajustes</Link><strong>{session.identity.first_name} {session.identity.last_name}</strong><small>{session.identity.email}</small></div>
          </aside>
          <main className="product-main" id="contenido" key={session.identity.id}>{children}</main>
        </div>
        <nav className="mobile-nav" aria-label="Navegación móvil">
          {mobileLinks.map(([href, , label]) => <Link data-active={pathname === href || pathname.startsWith(`${href}/`)} href={href} key={href}>{label}</Link>)}
        </nav>
      </div>
    </SessionContext.Provider>
  );
}
