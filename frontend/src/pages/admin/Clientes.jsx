import { useEffect, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatDateBR(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("pt-BR");
}

function StatusAtivoBadge({ ativo }) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        ativo ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
      }`}
    >
      {ativo ? "ATIVO" : "INATIVO"}
    </span>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-5 shadow-lg">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Fechar modal"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function Clientes() {
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [clientes, setClientes] = useState([]);
  const [isCreatingClient, setIsCreatingClient] = useState(false);
  const [provisioningClienteId, setProvisioningClienteId] = useState(null);
  const [formErrors, setFormErrors] = useState({});
  const [novoClienteData, setNovoClienteData] = useState({
    nome: "",
    razao_social: "",
    cnpj: "",
    email: "",
    whatsapp: "",
    criar_grupo: false,
    logo_url: "",
  });
  const [conexoesModal, setConexoesModal] = useState({
    open: false,
    clienteId: null,
    nome: "",
    google_customer_id: "",
    meta_ad_account_id: "",
  });
  const [isSavingConexoes, setIsSavingConexoes] = useState(false);
  const [cobrancaModal, setCobrancaModal] = useState({
    open: false,
    clienteId: null,
    nome: "",
    valor: "",
    descricao: "",
  });
  const [isCharging, setIsCharging] = useState(false);

  const clientesOrdenados = useMemo(() => clientes, [clientes]);

  async function carregarClientes() {
    try {
      setIsLoading(true);
      const response = await authFetch(`${API_BASE_URL}/admin/clientes`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar clientes.");
      setClientes(Array.isArray(payload) ? payload : []);
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao carregar clientes.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    carregarClientes();
  }, []);

  function updateNovoClienteField(field, value) {
    setNovoClienteData((prev) => ({ ...prev, [field]: value }));
  }

  async function handleCriarCliente(e) {
    e.preventDefault();
    const errors = {};
    const whatsappDigits = String(novoClienteData.whatsapp || "").replace(/\D/g, "");
    if (!String(novoClienteData.nome || "").trim()) errors.nome = "Informe o nome do cliente.";
    if (!String(novoClienteData.email || "").trim()) errors.email = "Informe o e-mail de acesso do cliente.";
    if (novoClienteData.criar_grupo && !whatsappDigits) {
      errors.whatsapp = "WhatsApp do cliente e obrigatorio quando a criacao de grupo esta ativa.";
    }
    if (novoClienteData.whatsapp && whatsappDigits.length < 12) {
      errors.whatsapp = "WhatsApp invalido. Use DDI+DDD+numero (ex: 5554999999999).";
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      toast.error("Corrija os campos do novo cliente antes de salvar.");
      return;
    }

    setFormErrors({});
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
      if (payload?.warning) toast.warning(payload.warning);
      setNovoClienteData({
        nome: "",
        razao_social: "",
        cnpj: "",
        email: "",
        whatsapp: "",
        criar_grupo: false,
        logo_url: "",
      });
      await carregarClientes();
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao criar cliente.");
    } finally {
      setIsCreatingClient(false);
    }
  }

  function abrirModalConexoes(cliente) {
    setConexoesModal({
      open: true,
      clienteId: cliente.id,
      nome: cliente.nome,
      google_customer_id: cliente.google_customer_id || "",
      meta_ad_account_id: cliente.meta_ad_account_id || "",
    });
  }

  async function salvarConexoes() {
    try {
      setIsSavingConexoes(true);
      const response = await authFetch(`${API_BASE_URL}/admin/clientes/${conexoesModal.clienteId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          google_customer_id: conexoesModal.google_customer_id,
          meta_ad_account_id: conexoesModal.meta_ad_account_id,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao salvar conexoes.");

      setClientes((prev) => prev.map((item) => (item.id === payload.id ? { ...item, ...payload } : item)));
      setConexoesModal((prev) => ({ ...prev, open: false }));
      toast.success("Conexões atualizadas com sucesso.");
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao salvar conexoes.");
    } finally {
      setIsSavingConexoes(false);
    }
  }

  function abrirModalCobranca(cliente) {
    setCobrancaModal({
      open: true,
      clienteId: cliente.id,
      nome: cliente.nome,
      valor: "",
      descricao: "",
    });
  }

  async function gerarCobranca() {
    const valor = Number(cobrancaModal.valor || 0);
    if (!valor || valor <= 0) {
      toast.error("Informe um valor valido para cobranca.");
      return;
    }
    if (!String(cobrancaModal.descricao || "").trim()) {
      toast.error("Informe a descricao da cobranca.");
      return;
    }

    try {
      setIsCharging(true);
      const response = await authFetch(`${API_BASE_URL}/admin/clientes/${cobrancaModal.clienteId}/cobrar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          valor,
          descricao: cobrancaModal.descricao,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha ao gerar cobranca.");
      setCobrancaModal((prev) => ({ ...prev, open: false }));
      toast.success("Cobrança gerada e enviada via WhatsApp!");
      if (payload?.url_pagamento) {
        window.open(payload.url_pagamento, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao gerar cobrança.");
    } finally {
      setIsCharging(false);
    }
  }

  async function handleProvisionarDominio(clienteId) {
    const slugDigitado = window.prompt("Digite o slug para o subdominio (ex: clinica-sorriso):");
    const slug = String(slugDigitado || "")
      .trim()
      .toLowerCase();
    if (!slug) return;

    try {
      setProvisioningClienteId(clienteId);
      const response = await authFetch(`${API_BASE_URL}/admin/infra/provisionar-dominio/${clienteId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug }),
      });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload?.detail;
        const errorMessage = typeof detail === "string" ? detail : detail?.mensagem || "Falha ao provisionar dominio.";
        throw new Error(errorMessage);
      }
      setClientes((prev) =>
        prev.map((cliente) =>
          cliente.id === clienteId
            ? {
                ...cliente,
                dominio_personalizado: payload?.dominio_personalizado || cliente.dominio_personalizado || null,
              }
            : cliente
        )
      );
      toast.success(`Dominio provisionado: ${payload?.dominio_personalizado || slug}`);
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao provisionar dominio.");
    } finally {
      setProvisioningClienteId(null);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card>
          <form onSubmit={handleCriarCliente} className="space-y-5">
            <FormSection
              title="Novo Cliente"
              description="Cadastre novos clientes e, se desejar, crie automaticamente o grupo de onboarding no WhatsApp."
            >
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input
                  label="Nome do Cliente"
                  placeholder="Ex: Oficina Auto Center"
                  value={novoClienteData.nome}
                  onChange={(e) => updateNovoClienteField("nome", e.target.value)}
                  error={formErrors.nome}
                />
                <Input
                  type="email"
                  label="E-mail de Acesso"
                  placeholder="cliente@empresa.com"
                  value={novoClienteData.email}
                  onChange={(e) => updateNovoClienteField("email", e.target.value)}
                  error={formErrors.email}
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
                  label="WhatsApp do Cliente"
                  placeholder="5554999999999"
                  value={novoClienteData.whatsapp}
                  onChange={(e) => updateNovoClienteField("whatsapp", e.target.value)}
                  error={formErrors.whatsapp}
                />
                <Input
                  label="Logo URL (Opcional)"
                  placeholder="https://seusite.com/logo.png"
                  value={novoClienteData.logo_url}
                  onChange={(e) => updateNovoClienteField("logo_url", e.target.value)}
                />
              </div>
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
            <Button type="submit" variant="primary" isLoading={isCreatingClient}>
              Cadastrar Cliente
            </Button>
          </form>
        </Card>

        <Card>
          <div className="mb-4">
            <h1 className="text-2xl font-bold text-slate-900">Gestão de Clientes</h1>
            <p className="mt-1 text-sm text-slate-500">Gestão de licenças, conexões de mídia, cobrança e domínio.</p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-3 py-3">ID</th>
                  <th className="px-3 py-3">Nome</th>
                  <th className="px-3 py-3">CNPJ</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Vencimento Licença</th>
                  <th className="px-3 py-3">Conexões (Google/Meta)</th>
                  <th className="px-3 py-3">Ações</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-8 text-center text-slate-500">
                      Carregando clientes...
                    </td>
                  </tr>
                ) : clientesOrdenados.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-8 text-center text-slate-500">
                      Nenhum cliente cadastrado.
                    </td>
                  </tr>
                ) : (
                  clientesOrdenados.map((cliente) => (
                    <tr key={cliente.id} className="border-b border-slate-100 align-top">
                      <td className="px-3 py-3 font-semibold text-slate-700">{cliente.id}</td>
                      <td className="px-3 py-3">
                        <p className="font-semibold text-slate-900">{cliente.nome}</p>
                        <p className="text-xs text-slate-500">WhatsApp: {cliente.whatsapp || "-"}</p>
                      </td>
                      <td className="px-3 py-3 text-slate-700">{cliente.cnpj || "-"}</td>
                      <td className="px-3 py-3">
                        <StatusAtivoBadge ativo={Boolean(cliente.status_ativo)} />
                      </td>
                      <td className="px-3 py-3 text-slate-700">{formatDateBR(cliente.data_vencimento_licenca)}</td>
                      <td className="px-3 py-3 text-xs text-slate-600">
                        <p>Google: {cliente.google_customer_id || "-"}</p>
                        <p>Meta: {cliente.meta_ad_account_id || "-"}</p>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button type="button" variant="outline" size="sm" onClick={() => abrirModalConexoes(cliente)}>
                            Conexões
                          </Button>
                          <Button type="button" variant="outline" size="sm" onClick={() => abrirModalCobranca(cliente)}>
                            💰 Cobrar
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            isLoading={provisioningClienteId === cliente.id}
                            onClick={() => handleProvisionarDominio(cliente.id)}
                          >
                            Provisionar Domínio
                          </Button>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">Domínio: {cliente.dominio_personalizado || "-"}</p>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {conexoesModal.open ? (
        <Modal title={`Editar Conexões - ${conexoesModal.nome}`} onClose={() => setConexoesModal((prev) => ({ ...prev, open: false }))}>
          <div className="space-y-4">
            <Input
              label="Google Customer ID"
              value={conexoesModal.google_customer_id}
              onChange={(e) => setConexoesModal((prev) => ({ ...prev, google_customer_id: e.target.value }))}
            />
            <Input
              label="Meta Ad Account ID"
              value={conexoesModal.meta_ad_account_id}
              onChange={(e) => setConexoesModal((prev) => ({ ...prev, meta_ad_account_id: e.target.value }))}
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setConexoesModal((prev) => ({ ...prev, open: false }))}>
                Cancelar
              </Button>
              <Button type="button" variant="primary" isLoading={isSavingConexoes} onClick={salvarConexoes}>
                Salvar
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}

      {cobrancaModal.open ? (
        <Modal title={`Cobrar Cliente - ${cobrancaModal.nome}`} onClose={() => setCobrancaModal((prev) => ({ ...prev, open: false }))}>
          <div className="space-y-4">
            <Input
              type="number"
              step="0.01"
              label="Valor (R$)"
              value={cobrancaModal.valor}
              onChange={(e) => setCobrancaModal((prev) => ({ ...prev, valor: e.target.value }))}
            />
            <Input
              label="Descrição"
              value={cobrancaModal.descricao}
              onChange={(e) => setCobrancaModal((prev) => ({ ...prev, descricao: e.target.value }))}
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setCobrancaModal((prev) => ({ ...prev, open: false }))}>
                Cancelar
              </Button>
              <Button type="button" variant="primary" isLoading={isCharging} onClick={gerarCobranca}>
                Confirmar Cobrança
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
