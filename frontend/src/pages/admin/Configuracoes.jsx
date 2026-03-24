import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const PIE_COLORS = ["#2563eb", "#14b8a6", "#7c3aed", "#f97316"];

function formatUSD(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 }).format(
    Number(value || 0)
  );
}

export default function Configuracoes() {
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isCreatingClient, setIsCreatingClient] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [novoClienteErrors, setNovoClienteErrors] = useState({});
  const [isLoadingStatsIA, setIsLoadingStatsIA] = useState(true);
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
  const [statsIA, setStatsIA] = useState({
    custo_total_ia: 0,
    tokens_total: 0,
    economia_gerada_ia: 0,
    roi_estimado_limpeza: 0,
    por_modelo: [],
  });
  const [sistemaConfig, setSistemaConfig] = useState({
    intraday_cleaner_enabled: false,
    admin_whatsapp_number: "",
  });

  function updateField(field, value) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  function updateNovoClienteField(field, value) {
    setNovoClienteData((prev) => ({ ...prev, [field]: value }));
  }

  async function salvarConfiguracaoSistema(updatePatch, loadingMessage = "Salvando configuração...") {
    const promise = authFetch(`${API_BASE_URL}/admin/configuracoes-sistema`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatePatch),
    }).then(async (response) => {
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao salvar configuração de sistema.");
      setSistemaConfig({
        intraday_cleaner_enabled: Boolean(payload?.intraday_cleaner_enabled),
        admin_whatsapp_number: String(payload?.admin_whatsapp_number || ""),
      });
      return payload;
    });
    return toast.promise(promise, {
      loading: loadingMessage,
      success: "Configuração de sistema atualizada.",
      error: (error) => error?.message || "Erro ao salvar configuração de sistema.",
    });
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        setIsLoadingStatsIA(true);
        const [configResponse, statsResponse, sistemaResponse] = await Promise.all([
          authFetch(`${API_BASE_URL}/admin/configuracoes`),
          authFetch(`${API_BASE_URL}/admin/stats-ia?periodo_dias=30`),
          authFetch(`${API_BASE_URL}/admin/configuracoes-sistema`),
        ]);
        if (!configResponse.ok) throw new Error("Falha ao carregar configuracoes.");
        if (!sistemaResponse.ok) throw new Error("Falha ao carregar configuracoes de sistema.");
        const payload = await configResponse.json();
        const payloadStats = statsResponse.ok ? await statsResponse.json() : null;
        const payloadSistema = await sistemaResponse.json();
        if (mounted) {
          setFormData({
            razao_social: payload.razao_social || "",
            cnpj: payload.cnpj || "",
            whatsapp: payload.whatsapp || "",
            meta_page_id: payload.meta_page_id || "",
          });
          if (payloadStats?.status === "sucesso") {
            setStatsIA({
              custo_total_ia: Number(payloadStats.custo_total_ia || 0),
              tokens_total: Number(payloadStats.tokens_total || 0),
              economia_gerada_ia: Number(payloadStats.economia_gerada_ia || 0),
              roi_estimado_limpeza: Number(payloadStats.roi_estimado_limpeza || 0),
              por_modelo: Array.isArray(payloadStats.por_modelo) ? payloadStats.por_modelo : [],
            });
          }
          setSistemaConfig({
            intraday_cleaner_enabled: Boolean(payloadSistema?.intraday_cleaner_enabled),
            admin_whatsapp_number: String(payloadSistema?.admin_whatsapp_number || ""),
          });
        }
      } catch (error) {
        console.error(error);
        if (mounted) toast.error("Erro ao carregar configurações.");
      } finally {
        if (mounted) {
          setIsLoading(false);
          setIsLoadingStatsIA(false);
        }
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

        <Card className="mt-6">
          <FormSection
            title="Saúde e Custos"
            description="Monitoramento do custo da IA, consumo de tokens e retorno estimado da automacao."
          >
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase text-slate-500">Custo Total de IA (Mês)</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {isLoadingStatsIA ? "..." : formatUSD(statsIA.custo_total_ia)}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase text-slate-500">Tokens Consumidos</p>
                <p className="mt-2 text-2xl font-bold text-slate-900">
                  {isLoadingStatsIA ? "..." : Number(statsIA.tokens_total || 0).toLocaleString("pt-BR")}
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase text-slate-500">Economia Gerada pela IA</p>
                <p className="mt-2 text-2xl font-bold text-emerald-600">
                  {isLoadingStatsIA ? "..." : formatUSD(statsIA.economia_gerada_ia)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  ROI estimado limpeza: {isLoadingStatsIA ? "..." : formatUSD(statsIA.roi_estimado_limpeza)}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-slate-200 p-4">
              <p className="mb-3 text-sm font-semibold text-slate-700">Distribuição de uso (GPT-4o vs GPT-4o-mini)</p>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={statsIA.por_modelo}
                      dataKey="tokens_total"
                      nameKey="modelo"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                    >
                      {(statsIA.por_modelo || []).map((entry, index) => (
                        <Cell key={`${entry.modelo}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value, name, props) => [
                        Number(value || 0).toLocaleString("pt-BR"),
                        `${props?.payload?.modelo || name}`,
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
                {(statsIA.por_modelo || []).map((item, index) => (
                  <span
                    key={item.modelo}
                    className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1"
                  >
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }}
                    />
                    {item.modelo}: {Number(item.tokens_total || 0).toLocaleString("pt-BR")} tokens
                  </span>
                ))}
              </div>
            </div>
          </FormSection>
        </Card>

        <Card className="mt-6">
          <FormSection
            title="Inteligência"
            description="Controles globais da automação de limpeza intra-day."
          >
            <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Ativar Limpeza Intra-day Automática (A cada 3h)
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Controle em tempo real da task agendada no Celery Beat.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={sistemaConfig.intraday_cleaner_enabled}
                  onClick={() =>
                    salvarConfiguracaoSistema(
                      { intraday_cleaner_enabled: !sistemaConfig.intraday_cleaner_enabled },
                      "Atualizando status da limpeza intra-day..."
                    )
                  }
                  className={`relative inline-flex h-7 w-14 items-center rounded-full transition ${
                    sistemaConfig.intraday_cleaner_enabled ? "bg-emerald-600" : "bg-slate-300"
                  }`}
                >
                  <span
                    className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                      sistemaConfig.intraday_cleaner_enabled ? "translate-x-8" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              <div className="max-w-md">
                <Input
                  label="Número do WhatsApp Admin"
                  placeholder="5554999999999"
                  value={sistemaConfig.admin_whatsapp_number}
                  onChange={(e) =>
                    setSistemaConfig((prev) => ({
                      ...prev,
                      admin_whatsapp_number: e.target.value,
                    }))
                  }
                  onBlur={(e) =>
                    salvarConfiguracaoSistema(
                      { admin_whatsapp_number: String(e.target.value || "").replace(/\D/g, "") || null },
                      "Atualizando WhatsApp do admin..."
                    )
                  }
                />
                <p className="mt-1 text-xs text-slate-500">Formato esperado: DDI+DDD+numero (somente dígitos).</p>
              </div>
            </div>
          </FormSection>
        </Card>
      </div>
    </div>
  );
}
