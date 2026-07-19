import { Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { navigationItems } from "./routes";
import { OverviewPage } from "../pages/OverviewPage";
import { OpportunityPage } from "../pages/OpportunityPage";
import { PilotPage } from "../pages/PilotPage";
import { EvidencePage } from "../pages/EvidencePage";
import { AuditPage } from "../pages/AuditPage";
import { PlaceholderPage } from "../pages/PlaceholderPage";
import { WorkflowPage } from "../pages/WorkflowPage";
import { SimulationPage } from "../pages/SimulationPage";

type Theme = "light" | "dark" | "system";

function resolveTheme(theme: Theme) {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("wt-theme") as Theme) || "system");

  useEffect(() => {
    document.documentElement.dataset.theme = resolveTheme(theme);
    localStorage.setItem("wt-theme", theme);
  }, [theme]);

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
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/workflow" element={<WorkflowPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/opportunity" element={<OpportunityPage />} />
          <Route path="/simulation" element={<SimulationPage />} />
          <Route path="/pilot" element={<PilotPage />} />
          <Route path="/audit" element={<AuditPage />} />
          {navigationItems.filter((item) => !["/", "/workflow", "/evidence", "/opportunity", "/simulation", "/pilot", "/audit"].includes(item.path)).map((item) => (
            <Route key={item.path} path={item.path} element={<PlaceholderPage title={item.label} />} />
          ))}
          <Route path="*" element={<PlaceholderPage title="Page not found" />} />
        </Routes>
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
