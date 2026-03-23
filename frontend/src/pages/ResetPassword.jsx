import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import { useToast } from "../components/ui/ToastProvider";
import { authFetch, getStoredAuth, setStoredAuth } from "../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function ResetPassword() {
  const toast = useToast();
  const navigate = useNavigate();
  const auth = getStoredAuth();
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState({
    new_password: "",
    confirm_password: "",
  });

  if (!auth?.user) {
    return <Navigate to="/login" replace />;
  }
  if (!auth?.user?.needs_password_change) {
    return <Navigate to={auth.user.role === "ADMIN" ? "/admin/dashboard" : "/dashboard"} replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (form.new_password !== form.confirm_password) {
      toast.error("A confirmacao da senha nao confere.");
      return;
    }

    try {
      setIsSaving(true);
      const response = await authFetch(`${API_BASE_URL}/auth/update-password`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao atualizar senha.");

      setStoredAuth(payload);
      toast.success("Senha atualizada com sucesso.");
      navigate(payload?.user?.role === "ADMIN" ? "/admin/dashboard" : "/dashboard", { replace: true });
      window.location.reload();
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao atualizar senha.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <Card className="w-full max-w-md">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Redefinir Senha</h1>
            <p className="mt-1 text-sm text-slate-500">
              No primeiro acesso, voce precisa definir uma senha propria antes de continuar.
            </p>
          </div>

          <Input
            type="password"
            label="Nova Senha"
            value={form.new_password}
            onChange={(e) => setForm((prev) => ({ ...prev, new_password: e.target.value }))}
            required
          />
          <Input
            type="password"
            label="Confirmar Nova Senha"
            value={form.confirm_password}
            onChange={(e) => setForm((prev) => ({ ...prev, confirm_password: e.target.value }))}
            required
          />

          <Button type="submit" variant="primary" isLoading={isSaving}>
            Salvar Nova Senha
          </Button>
        </form>
      </Card>
    </div>
  );
}
