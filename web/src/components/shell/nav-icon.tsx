import {
  Blocks,
  Building2,
  Compass,
  Database,
  FileSearch,
  FileText,
  Gavel,
  Inbox,
  Layers,
  LayoutGrid,
  LineChart,
  ListChecks,
  Scale,
  ScrollText,
  Settings2,
  ShieldCheck,
  Upload,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type { NavIcon as NavIconName } from "@/lib/nav";

const ICONS: Record<NavIconName, LucideIcon> = {
  workbench: Compass,
  overview: LayoutGrid,
  entities: Building2,
  findings: FileSearch,
  queue: ListChecks,
  decisions: Gavel,
  analytics: LineChart,
  benchmarks: Scale,
  pipeline: Workflow,
  submissions: Inbox,
  ingest: Upload,
  securityData: Database,
  agents: Blocks,
  architecture: Layers,
  reports: FileText,
  trust: ShieldCheck,
  audit: ScrollText,
  admin: Users,
  system: Settings2,
};

export function NavIcon({ name, className }: { name: NavIconName; className?: string }) {
  const Icon = ICONS[name];
  return <Icon className={className} aria-hidden="true" strokeWidth={1.75} />;
}
