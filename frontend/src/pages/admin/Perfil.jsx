import { useEffect, useState } from "react";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch, getStoredAuth, setStoredAuth } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Perfil() {
  const toast = useToast();
  const auth = getStoredAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });

  useEffect(() => {
    async function loadProfile() {
      try {
        setIsLoading(true);
        const response = await authFetch(`${API_BASE_URL}/auth/me`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar perfil.");
        setProfile(payload.user);
      } catch (error) {
        console.error(error);
        toast.error(error?.message || "Erro ao carregar perfil.");
      } finally {
        setIsLoading(false);
      }
    }

    loadProfile();
  }, [toast]);

  async function handleUpdatePassword(e) {
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

      setStoredAuth({
        ...payload,
        user: {
          ...payload.user,
          nome: profile?.nome || auth?.user?.nome,
        },
      });
      setProfile((prev) => ({
        ...prev,
        needs_password_change: false,
      }));
      setForm({
        current_password: "",
        new_password: "",
        confirm_password: "",
      });
      toast.success("Senha alterada com sucesso.");
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao alterar senha.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
        <div className="grid gap-6 md:grid-cols-2">
          <div className="h-56 animate-pulse rounded-xl bg-slate-200" />
          <div className="h-56 animate-pulse rounded-xl bg-slate-200" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Perfil do Usuario</h1>
        <p className="mt-1 text-sm text-slate-500">Consulte seus dados basicos e atualize sua senha quando desejar.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <FormSection title="Dados da Conta" description="Informacoes basicas do usuario autenticado.">
            <Input label="Nome" value={profile?.nome || "-"} disabled />
            <Input label="E-mail" value={profile?.email || ""} disabled />
            <Input label="Perfil" value={profile?.role || ""} disabled />
          </FormSection>
        </Card>

        <Card>
          <form onSubmit={handleUpdatePassword}>
            <FormSection title="Alterar Senha" description="Informe sua senha atual e defina uma nova senha segura.">
              <Input
                type="password"
                label="Senha Atual"
                value={form.current_password}
                onChange={(e) => setForm((prev) => ({ ...prev, current_password: e.target.value }))}
                required
              />
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
                Atualizar Senha
              </Button>
            </FormSection>
          </form>
        </Card>
      </div>
    </div>
  );
}
