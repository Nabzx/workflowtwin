import { Menu, Moon, Sun, X } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { navigationItems } from "./routes";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PageLoading } from "../components/PageState";
import { NotFoundPage } from "../pages/NotFoundPage";

const OverviewPage = lazy(() => import("../pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const WorkflowPage = lazy(() => import("../pages/WorkflowPage").then((module) => ({ default: module.WorkflowPage })));
const EvidencePage = lazy(() => import("../pages/EvidencePage").then((module) => ({ default: module.EvidencePage })));
const OpportunityPage = lazy(() => import("../pages/OpportunityPage").then((module) => ({ default: module.OpportunityPage })));
const SimulationPage = lazy(() => import("../pages/SimulationPage").then((module) => ({ default: module.SimulationPage })));
const PilotPage = lazy(() => import("../pages/PilotPage").then((module) => ({ default: module.PilotPage })));
const AuditPage = lazy(() => import("../pages/AuditPage").then((module) => ({ default: module.AuditPage })));
const EngineeringPage = lazy(() => import("../pages/EngineeringPage").then((module) => ({ default: module.EngineeringPage })));

type Theme = "light" | "dark" | "system";

function resolveTheme(theme: Theme) {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("wt-theme") as Theme) || "system");

  useEffect(() => {
    document.documentElement.dataset.theme = resolveTheme(theme);
    localStorage.setItem("wt-theme", theme);
    if (theme !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => { document.documentElement.dataset.theme = resolveTheme("system"); };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [theme]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const cycleTheme = () => setTheme((current) => (current === "system" ? "light" : current === "light" ? "dark" : "system"));

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="mobile-header">
        <button className="icon-button" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu /></button>
        <Brand />
        <ThemeButton theme={theme} onClick={cycleTheme} />
      </header>
      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`} aria-label="Primary navigation">
        <div className="sidebar__header">
          <Brand />
          <button className="icon-button sidebar__close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X /></button>
        </div>
        <p className="fictional-label">Fictional operations demo</p>
        <nav>
          {navigationItems.map(({ label, path, icon: Icon }) => (
            <NavLink key={path} to={path} end={path === "/"} onClick={() => setMenuOpen(false)}>
              <Icon aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <ThemeButton theme={theme} onClick={cycleTheme} />
          <span>{theme} mode</span>
        </div>
      </aside>
      {menuOpen && <button className="scrim" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />}
      <main id="main-content" className="main-content">
        {!online && <div className="offline-banner" role="status">API unavailable while offline. Existing content may be stale.</div>}
        <ErrorBoundary><Suspense fallback={<PageLoading />}><Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/workflow" element={<WorkflowPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/opportunity" element={<OpportunityPage />} />
          <Route path="/simulation" element={<SimulationPage />} />
          <Route path="/pilot" element={<PilotPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/engineering" element={<EngineeringPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes></Suspense></ErrorBoundary>
      </main>
    </div>
  );
}

function Brand() {
  return <div className="brand"><span className="brand__mark">WT</span><span>WorkflowTwin</span></div>;
}

function ThemeButton({ theme, onClick }: { theme: Theme; onClick: () => void }) {
  return (
    <button className="icon-button" onClick={onClick} aria-label={`Theme: ${theme}. Change theme`} title={`Theme: ${theme}`}>
      {theme === "dark" ? <Moon /> : <Sun />}
    </button>
  );
}
