import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useToast } from "../ui/ToastProvider";
import { clearStoredAuth, getStoredAuth } from "../../lib/auth";

function UserIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-4.42 0-8 2.24-8 5v1h16v-1c0-2.76-3.58-5-8-5Z"
        className="fill-current"
      />
    </svg>
  );
}

function SettingsIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="m14.5 4 .7 1.9a6.8 6.8 0 0 1 1.3.8l1.9-.6 1.4 2.4-1.5 1.3c.1.4.1.8.1 1.2s0 .8-.1 1.2l1.5 1.3-1.4 2.4-1.9-.6c-.4.3-.8.6-1.3.8L14.5 20h-3l-.7-1.9a6.8 6.8 0 0 1-1.3-.8l-1.9.6-1.4-2.4 1.5-1.3A5.5 5.5 0 0 1 7.6 12c0-.4 0-.8.1-1.2L6.2 9.5l1.4-2.4 1.9.6c.4-.3.8-.6 1.3-.8L11.5 4h3Zm-1 8a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0Z"
        className="fill-current"
      />
    </svg>
  );
}

function LogOutIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M9 4h-3a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3v-2h-3V6h3V4Zm5.6 3.4L13.2 8.8 15.4 11H8v2h7.4l-2.2 2.2 1.4 1.4L19.2 12l-4.6-4.6Z"
        className="fill-current"
      />
    </svg>
  );
}

function ActivityIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M3 12h4l2-5 4 10 2-5h6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDownIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function UserMenu() {
  const toast = useToast();
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const auth = getStoredAuth();
  const user = auth?.user;
  const role = user?.role;

  const displayName = useMemo(() => {
    const nome = String(user?.nome || "").trim();
    if (nome) return nome;
    return String(user?.email || "Usuario");
  }, [user?.nome, user?.email]);

  const avatarLetter = useMemo(() => {
    return (displayName[0] || "U").toUpperCase();
  }, [displayName]);

  useEffect(() => {
    if (!isOpen) return undefined;

    function handleOutsideClick(event) {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  function handleLogout() {
    setIsOpen(false);
    clearStoredAuth();
    window.localStorage.removeItem("token");
    window.localStorage.removeItem("role");
    window.localStorage.removeItem("user");
    toast.info("Sessao encerrada.");
    navigate("/login", { replace: true });
  }

  function handleSelect() {
    setIsOpen(false);
  }

  if (!user) return null;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 shadow-sm transition hover:bg-slate-50"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
          {avatarLetter}
        </span>
        <span className="hidden max-w-[180px] truncate text-xs text-slate-600 sm:block">{displayName}</span>
        <ChevronDownIcon className="h-4 w-4 text-slate-500" />
      </button>

      <div
        className={`absolute right-0 z-40 mt-2 w-56 origin-top-right rounded-xl border border-slate-200 bg-white p-2 shadow-lg transition-all duration-150 ${
          isOpen ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0"
        }`}
      >
        <Link
          to="/admin/perfil"
          onClick={handleSelect}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          <UserIcon />
          Meu Perfil
        </Link>

        {role === "ADMIN" ? (
          <Link
            to="/admin/configuracoes"
            onClick={handleSelect}
            className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            <SettingsIcon />
            Configuracoes
          </Link>
        ) : null}
        {role === "ADMIN" ? (
          <Link
            to="/admin/logs"
            onClick={handleSelect}
            className="mt-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            <ActivityIcon />
            Logs de Atividade
          </Link>
        ) : null}

        <hr className="my-2 border-slate-200" />

        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
        >
          <LogOutIcon />
          Sair
        </button>
      </div>
    </div>
  );
}
