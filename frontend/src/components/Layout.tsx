import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, List, Factory, Package, TrendingUp, MessageSquare, Gauge, Menu, X } from "lucide-react";
import brand from "../brand";
import { FEATURES } from "../features";

const INZICHT = [
  { to: "/", label: "Overzicht", icon: LayoutDashboard },
  { to: "/alarms", label: "Alarmen", icon: List },
  { to: "/production", label: "Productie", icon: Factory },
  // Pallets: feature-flag uit (hoort niet bij deze lijn). Aanzetten in features.ts.
  ...(FEATURES.pallets ? [{ to: "/pallets", label: "Pallets", icon: Package }] : []),
  { to: "/trends", label: "Trends", icon: TrendingUp },
  { to: "/chat", label: "Chat", icon: MessageSquare },
];

const MAINTENANCE = [
  { to: "/maintenance", label: "Motoren", icon: Gauge },
] as const;

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const renderGroup = (title: string, items: readonly { to: string; label: string; icon: typeof Gauge }[]) => (
    <div>
      <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-wider text-dgs-100/40">
        {title}
      </p>
      <div className="space-y-1">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-white/15 text-white"
                  : "text-dgs-100/70 hover:bg-white/10 hover:text-white"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </div>
    </div>
  );

  const sidebar = (
    <>
      <div className="px-5 py-5 border-b border-dgs-700">
        {brand.logo ? (
          <img src={brand.logo} alt={brand.appName} className="h-7" />
        ) : (
          <span className="text-xl font-bold tracking-tight text-white">{brand.appName}</span>
        )}
        <p className="text-xs text-dgs-100/70 mt-1">{brand.subtitle}</p>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {renderGroup("Inzicht", INZICHT)}
        {FEATURES.maintenance && renderGroup("Maintenance", MAINTENANCE)}
      </nav>
      <div className="px-5 py-4 border-t border-dgs-700 text-xs text-dgs-100/50">
        {brand.footer}
      </div>
    </>
  );

  return (
    <div className="flex h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 bg-dgs-900 text-white flex-col shrink-0">
        {sidebar}
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-56 bg-dgs-900 text-white flex flex-col transform transition-transform md:hidden ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <button
          onClick={() => setSidebarOpen(false)}
          className="absolute top-4 right-4 text-white/70 hover:text-white"
        >
          <X size={20} />
        </button>
        {sidebar}
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg hover:bg-gray-100"
          >
            <Menu size={20} className="text-gray-600" />
          </button>
          <span className="text-lg font-bold text-gray-800">{brand.appName}</span>
        </header>

        <main className="flex-1 overflow-y-auto bg-gray-50 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
