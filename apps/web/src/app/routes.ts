import {
  BarChart3,
  Blocks,
  FlaskConical,
  Gauge,
  GitBranch,
  History,
  Lightbulb,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

export const navigationItems: NavigationItem[] = [
  { label: "Overview", path: "/", icon: Gauge },
  { label: "Workflow", path: "/workflow", icon: GitBranch },
  { label: "Evidence", path: "/evidence", icon: BarChart3 },
  { label: "Opportunity", path: "/opportunity", icon: Lightbulb },
  { label: "Simulation", path: "/simulation", icon: FlaskConical },
  { label: "Pilot", path: "/pilot", icon: ShieldCheck },
  { label: "Audit and Gates", path: "/audit", icon: History },
  { label: "Engineering", path: "/engineering", icon: Blocks },
];

