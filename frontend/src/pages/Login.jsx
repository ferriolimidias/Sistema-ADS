import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import { useToast } from "../components/ui/ToastProvider";
import { getStoredAuth, setStoredAuth } from "../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Login() {
  const toast = useToast();
  const navigate = useNavigate();
  const auth = getStoredAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [form, setForm] = useState({ email: "", password: "" });

  if (auth?.user?.needs_password_change) {
    return <Navigate to="/redefinir-senha" replace />;
  }
  if (auth?.user?.role === "ADMIN") {
    return <Navigate to="/admin/dashboard" replace />;
  }
  if (auth?.user?.role === "CLIENTE") {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha no login.");

      setStoredAuth(payload);

      if (payload?.user?.needs_password_change) {
        navigate("/redefinir-senha", { replace: true });
      } else if (payload?.user?.role === "ADMIN") {
        navigate("/admin/dashboard", { replace: true });
      } else {
        navigate("/dashboard", { replace: true });
      }
      window.location.reload();
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao entrar.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <Card className="w-full max-w-md">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <div className="mb-4 inline-flex items-center gap-3 rounded-full bg-slate-100 px-4 py-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                FM
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">Ferrioli Midias</p>
                <p className="text-xs text-slate-500">Painel de Performance</p>
              </div>
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Login</h1>
            <p className="mt-1 text-sm text-slate-500">
              Entre com suas credenciais para acessar o painel.
            </p>
          </div>

          <Input
            type="email"
            label="E-mail"
            value={form.email}
            onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
            placeholder="cliente@empresa.com"
            required
          />
          <Input
            type="password"
            label="Senha"
            value={form.password}
            onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
            placeholder="Sua senha"
            required
          />

          <Button type="submit" variant="primary" isLoading={isLoading}>
            Entrar
          </Button>
        </form>
      </Card>
    </div>
  );
}
