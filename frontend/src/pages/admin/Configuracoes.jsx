import { useEffect, useState } from "react";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Configuracoes() {
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCreatingClient, setIsCreatingClient] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [novoClienteErrors, setNovoClienteErrors] = useState({});
  const [formData, setFormData] = useState({
    razao_social: "",
    cnpj: "",
    whatsapp: "",
    meta_page_id: "",
  });
  const [novoClienteData, setNovoClienteData] = useState({
    nome: "",
    razao_social: "",
    cnpj: "",
    email: "",
    whatsapp: "",
    criar_grupo: false,
    logo_url: "",
  });

  function updateField(field, value) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  function updateNovoClienteField(field, value) {
    setNovoClienteData((prev) => ({ ...prev, [field]: value }));
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        const response = await authFetch(`${API_BASE_URL}/admin/configuracoes`);
        if (!response.ok) throw new Error("Falha ao carregar configuracoes.");
        const payload = await response.json();
        if (mounted) {
          setFormData({
            razao_social: payload.razao_social || "",
            cnpj: payload.cnpj || "",
            whatsapp: payload.whatsapp || "",
            meta_page_id: payload.meta_page_id || "",
          });
        }
      } catch (error) {
        console.error(error);
        if (mounted) toast.error("Erro ao carregar configurações.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const errors = {};
    const whatsappDigits = String(formData.whatsapp || "").replace(/\D/g, "");
    if (formData.whatsapp && whatsappDigits.length < 12) {
      errors.whatsapp = "Informe no formato DDI+DDD+numero, sem simbolos (ex: 5554999999999).";
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      toast.error("Corrija os campos destacados antes de salvar.");
      return;
    }

    setFormErrors({});

    try {
      setIsSaving(true);
      const response = await authFetch(`${API_BASE_URL}/admin/configuracoes`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          razao_social: formData.razao_social,
          cnpj: formData.cnpj,
          whatsapp: whatsappDigits,
          meta_page_id: formData.meta_page_id,
        }),
      });
      if (!response.ok) throw new Error("Falha ao salvar configuracoes.");
      toast.success("Configurações salvas com sucesso.");
    } catch (error) {
      console.error(error);
      toast.error("Erro ao salvar configurações.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCriarCliente(e) {
    e.preventDefault();
    const errors = {};
    const whatsappDigits = String(novoClienteData.whatsapp || "").replace(/\D/g, "");
    if (!String(novoClienteData.nome || "").trim()) {
      errors.nome = "Informe o nome do cliente.";
    }
    if (!String(novoClienteData.email || "").trim()) {
      errors.email = "Informe o e-mail de acesso do cliente.";
    }
    if (novoClienteData.criar_grupo && !whatsappDigits) {
      errors.whatsapp = "WhatsApp do cliente e obrigatorio quando a criacao de grupo esta ativa.";
    }
    if (novoClienteData.whatsapp && whatsappDigits.length < 12) {
      errors.whatsapp = "WhatsApp invalido. Use DDI+DDD+numero (ex: 5554999999999).";
    }

    if (Object.keys(errors).length > 0) {
      setNovoClienteErrors(errors);
      toast.error("Corrija os campos do novo cliente antes de salvar.");
      return;
    }

    setNovoClienteErrors({});

    try {
      setIsCreatingClient(true);
      const response = await authFetch(`${API_BASE_URL}/admin/clientes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nome: novoClienteData.nome,
          razao_social: novoClienteData.razao_social,
          cnpj: novoClienteData.cnpj,
          email: novoClienteData.email,
          whatsapp: whatsappDigits || null,
          criar_grupo: novoClienteData.criar_grupo,
          logo_url: novoClienteData.logo_url || null,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao criar cliente.");

      toast.success("Cliente criado com sucesso.");
      if (payload?.warning) {
        toast.warning(payload.warning);
      }
      setNovoClienteData({
        nome: "",
        razao_social: "",
        cnpj: "",
        email: "",
        whatsapp: "",
        criar_grupo: false,
        logo_url: "",
      });
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao criar cliente.");
    } finally {
      setIsCreatingClient(false);
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="mx-auto max-w-4xl">
          <div className="h-40 animate-pulse rounded-xl bg-slate-200" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
              <p className="mt-1 text-sm text-slate-500">
                Defina os dados globais para integração com plataformas de anúncios.
              </p>
            </div>

            <FormSection
              title="Dados Exibidos nas Landing Pages"
              description="Esses campos sao usados no rodape das paginas e na geracao do link de atendimento."
            >
              <Input
                label="Razao Social (Exibida no Rodape da LP)"
                placeholder="Ex: Ferrioli Midia e Performance LTDA"
                value={formData.razao_social}
                onChange={(e) => updateField("razao_social", e.target.value)}
              />
              <Input
                label="CNPJ (Exibida no Rodape da LP)"
                placeholder="Ex: 12.345.678/0001-90"
                value={formData.cnpj}
                onChange={(e) => updateField("cnpj", e.target.value)}
              />
              <Input
                label="WhatsApp (DDI + DDD + Numero)"
                placeholder="5554999999999"
                value={formData.whatsapp}
                onChange={(e) => updateField("whatsapp", e.target.value)}
                error={formErrors.whatsapp}
              />
              <p className="text-xs text-slate-500">
                Use apenas numeros, sem parenteses, espacos ou tracos.
              </p>
            </FormSection>

            <FormSection
              title="Meta Ads"
              description="Preencha o Page ID usado para criação de criativos no lançamento automático."
            >
              <Input
                label="Meta Page ID"
                placeholder="Ex: 123456789012345"
                value={formData.meta_page_id}
                onChange={(e) => updateField("meta_page_id", e.target.value)}
              />
            </FormSection>

            <div>
              <Button type="submit" variant="primary" isLoading={isSaving}>
                Salvar Configurações
              </Button>
            </div>
          </form>
        </Card>

        <Card className="mt-6">
          <form onSubmit={handleCriarCliente} className="space-y-6">
            <FormSection
              title="Novo Cliente"
              description="Cadastre novos clientes e, se desejar, crie automaticamente o grupo de onboarding no WhatsApp."
            >
              <Input
                label="Nome do Cliente"
                placeholder="Ex: Oficina Auto Center"
                value={novoClienteData.nome}
                onChange={(e) => updateNovoClienteField("nome", e.target.value)}
                error={novoClienteErrors.nome}
              />
              <Input
                label="Razao Social"
                placeholder="Ex: Oficina Auto Center LTDA"
                value={novoClienteData.razao_social}
                onChange={(e) => updateNovoClienteField("razao_social", e.target.value)}
              />
              <Input
                label="CNPJ"
                placeholder="Ex: 12.345.678/0001-90"
                value={novoClienteData.cnpj}
                onChange={(e) => updateNovoClienteField("cnpj", e.target.value)}
              />
              <Input
                type="email"
                label="E-mail de Acesso"
                placeholder="cliente@empresa.com"
                value={novoClienteData.email}
                onChange={(e) => updateNovoClienteField("email", e.target.value)}
                error={novoClienteErrors.email}
              />
              <Input
                label="WhatsApp do Cliente"
                placeholder="5554999999999"
                value={novoClienteData.whatsapp}
                onChange={(e) => updateNovoClienteField("whatsapp", e.target.value)}
                error={novoClienteErrors.whatsapp}
              />
              <Input
                label="Logo URL (Opcional)"
                placeholder="https://seusite.com/logo.png"
                value={novoClienteData.logo_url}
                onChange={(e) => updateNovoClienteField("logo_url", e.target.value)}
              />

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={novoClienteData.criar_grupo}
                  onChange={(e) => updateNovoClienteField("criar_grupo", e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Criar Grupo de WhatsApp Automaticamente?
              </label>
            </FormSection>

            <div>
              <Button type="submit" variant="primary" isLoading={isCreatingClient}>
                Cadastrar Cliente
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
