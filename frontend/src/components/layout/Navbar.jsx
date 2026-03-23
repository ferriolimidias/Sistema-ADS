import { Link, useLocation } from "react-router-dom";

import UserMenu from "./UserMenu";
import { getStoredAuth } from "../../lib/auth";

function NavItem({ to, label, active }) {
  return (
    <Link
      to={to}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
        active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      }`}
    >
      {label}
    </Link>
  );
}

export default function Navbar() {
  const location = useLocation();
  const auth = getStoredAuth();
  const role = auth?.user?.role;
  const isAuthenticated = Boolean(auth?.user);

  if (!isAuthenticated) return null;

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link to={role === "ADMIN" ? "/admin/dashboard" : "/dashboard"} className="text-sm font-bold text-slate-900">
            Ferrioli Midias
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            <NavItem
              to={role === "ADMIN" ? "/admin/dashboard" : "/dashboard"}
              label="Dashboard"
              active={location.pathname === "/dashboard" || location.pathname === "/admin" || location.pathname === "/admin/dashboard"}
            />
            {role === "ADMIN" ? (
              <>
                <NavItem to="/admin/campanhas/nova" label="Nova Campanha" active={location.pathname === "/admin/campanhas/nova"} />
                <NavItem to="/admin/configuracoes" label="Configuracoes" active={location.pathname === "/admin/configuracoes"} />
                <NavItem to="/admin/limpeza-termos" label="Limpeza de Termos" active={location.pathname === "/admin/limpeza-termos"} />
                <NavItem to="/admin/logs" label="Logs de Atividade" active={location.pathname === "/admin/logs"} />
              </>
            ) : null}
          </nav>
        </div>
        <UserMenu />
      </div>
    </header>
  );
}
