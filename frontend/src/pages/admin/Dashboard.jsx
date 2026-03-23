import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import ServiceBreakdownChart from "../../components/charts/ServiceBreakdownChart";
import ServiceRankingTable from "../../components/dashboard/ServiceRankingTable";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch, getStoredAuth } from "../../lib/auth";
import usePerformance from "../../hooks/usePerformance";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, idx) => (
            <Card key={idx}>
              <Skeleton className="h-4 w-28" />
              <Skeleton className="mt-3 h-8 w-36" />
              <Skeleton className="mt-2 h-3 w-24" />
            </Card>
          ))}
        </div>
        <Card>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="mt-2 h-4 w-72" />
          <Skeleton className="mt-4 h-10 w-48" />
        </Card>
      </div>
    </div>
  );
}

function formatBRL(value) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numeric);
}

export default function Dashboard() {
  const toast = useToast();
  const navigate = useNavigate();
  const auth = getStoredAuth();
  const isAdmin = auth?.user?.role === "ADMIN";
  const [campanhaSelecionadaId, setCampanhaSelecionadaId] = useState(null);
  const {
    data,
    isLoading: isLoadingPerformance,
    error: performanceError,
    periodoDias,
    setPeriodoDias,
    reloadPerformance,
  } = usePerformance({ isAdmin, campanhaId: campanhaSelecionadaId });
  const [isLoadingCampanhas, setIsLoadingCampanhas] = useState(true);
  const [isRegistering, setIsRegistering] = useState(false);
  const [sendingPorCampanha, setSendingPorCampanha] = useState({});
  const [isVendaModalOpen, setIsVendaModalOpen] = useState(false);
  const [campanhas, setCampanhas] = useState([]);
  const [vendaForm, setVendaForm] = useState({ campanha_id: "", valor: "" });

  async function carregarCampanhas() {
    const url = isAdmin ? `${API_BASE_URL}/admin/campanhas` : `${API_BASE_URL}/client/campanhas`;
    const response = await authFetch(url);
    if (!response.ok) throw new Error("Falha ao carregar campanhas.");
    const payload = await response.json();
    setCampanhas(Array.isArray(payload) ? payload : []);
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoadingCampanhas(true);
        await carregarCampanhas();
      } catch (error) {
        console.error(error);
        if (mounted) toast.error("Erro ao carregar Dashboard.");
      } finally {
        if (mounted) setIsLoadingCampanhas(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (campanhaSelecionadaId) return;
    if (!Array.isArray(campanhas) || campanhas.length === 0) return;
    const primeiraCampanha = campanhas[0];
    if (primeiraCampanha?.id) {
      setCampanhaSelecionadaId(primeiraCampanha.id);
    }
  }, [campanhas, campanhaSelecionadaId]);

  useEffect(() => {
    if (performanceError) {
      toast.error("Erro ao carregar performance consolidada.");
    }
  }, [performanceError, toast]);

  async function handleRegistrarVenda(e) {
    e.preventDefault();
    if (!vendaForm.campanha_id || !vendaForm.valor || Number(vendaForm.valor) <= 0) {
      toast.error("Informe campanha e valor de venda valido.");
      return;
    }

    try {
      setIsRegistering(true);
      const response = await authFetch(`${API_BASE_URL}/admin/registrar-venda`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          campanha_id: Number(vendaForm.campanha_id),
          valor: Number(vendaForm.valor),
        }),
      });
      if (!response.ok) throw new Error("Falha ao registrar venda.");

      await reloadPerformance();
      toast.success("Venda registrada com sucesso.");
      setIsVendaModalOpen(false);
      setVendaForm({ campanha_id: "", valor: "" });
    } catch (error) {
      console.error(error);
      toast.error("Erro ao registrar venda.");
    } finally {
      setIsRegistering(false);
    }
  }

  async function handleEnviarGrupo(campanhaId) {
    try {
      setSendingPorCampanha((prev) => ({ ...prev, [campanhaId]: true }));
      const response = await authFetch(`${API_BASE_URL}/admin/enviar-relatorio-whatsapp/${campanhaId}`, {
        method: "POST",
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || "Falha ao enviar relatorio no WhatsApp.");
      }
      toast.success("Relatorio enviado no grupo com sucesso.");
    } catch (error) {
      console.error(error);
      toast.error(error?.message || "Erro ao enviar relatorio no WhatsApp.");
    } finally {
      setSendingPorCampanha((prev) => ({ ...prev, [campanhaId]: false }));
    }
  }

  const roasLabel = useMemo(() => {
    const roas = Number(data.roas_geral);
    if (!Number.isFinite(roas) || roas <= 0) return "0.0x";
    return `${roas.toFixed(1)}x`;
  }, [data.roas_geral]);

  const roasClass = useMemo(() => {
    const roas = Number(data.roas_geral || 0);
    if (roas > 3) return "text-green-600";
    if (roas < 1) return "text-red-600";
    return "text-slate-900";
  }, [data.roas_geral]);

  const breakdownServicos = Array.isArray(data.breakdown_servicos) ? data.breakdown_servicos : [];
  const temBreakdownServicos = breakdownServicos.length > 0;
  const isLoading = isLoadingPerformance || isLoadingCampanhas;

  if (isLoading) return <DashboardSkeleton />;

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm font-medium text-slate-500">Gasto Total</p>
            <p className="mt-2 text-2xl font-bold text-slate-900">{formatBRL(data.gasto_total)}</p>
          </Card>

          <Card>
            <p className="text-sm font-medium text-slate-500">Faturamento (AgenteSO)</p>
            <p className="mt-2 text-2xl font-bold text-green-600">{formatBRL(data.receita_total)}</p>
            <p className="mt-1 text-xs font-medium text-green-600">↑ Receita em crescimento</p>
            {isAdmin ? (
              <div className="mt-3">
                <Button variant="outline" size="sm" onClick={() => setIsVendaModalOpen(true)}>
                  + Registrar Venda
                </Button>
              </div>
            ) : null}
          </Card>

          <Card>
            <p className="text-sm font-medium text-slate-500">Leads Convertidos</p>
            <p className="mt-2 text-2xl font-bold text-slate-900">{Number(data.total_leads || 0)}</p>
          </Card>

          <Card>
            <p className="text-sm font-medium text-slate-500">ROAS Real</p>
            <p className={`mt-2 text-2xl font-bold ${roasClass}`}>{roasLabel}</p>
          </Card>
        </div>

        <Card>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Analise por Oferta/Servico</h2>
              <p className="mt-1 text-sm text-slate-500">
                Acompanhe gasto e eficiencia por STAG com base na coleta granular.
              </p>
            </div>
            <div className="w-full max-w-[220px] space-y-1">
              <label className="block text-sm font-medium text-slate-700">Periodo</label>
              <select
                value={periodoDias}
                onChange={(e) => setPeriodoDias(Number(e.target.value))}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value={7}>Ultimos 7 dias</option>
                <option value={30}>Ultimos 30 dias</option>
                <option value={90}>Ultimos 90 dias</option>
              </select>
            </div>
            {isAdmin ? (
              <div className="w-full max-w-[280px] space-y-1">
                <label className="block text-sm font-medium text-slate-700">Campanha para Otimizacao</label>
                <select
                  value={campanhaSelecionadaId || ""}
                  onChange={(e) => setCampanhaSelecionadaId(Number(e.target.value) || null)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Selecione uma campanha</option>
                  {campanhas.map((campanha) => (
                    <option key={campanha.id} value={campanha.id}>
                      #{campanha.id} - {campanha.cliente_nome} ({campanha.plataforma})
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </div>

          <div className="mt-4">
            {!temBreakdownServicos ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                <p className="text-sm font-medium text-slate-700">Aguardando coleta granular...</p>
                <p className="mt-1 text-xs text-slate-500">
                  Assim que as metricas por servico estiverem disponiveis, o grafico e ranking serao exibidos aqui.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                <Card>
                  <FormSection
                    title="Performance por Servico"
                    description="Barras representam gasto e linha representa ROAS."
                  >
                    <ServiceBreakdownChart data={breakdownServicos} />
                  </FormSection>
                </Card>
                <Card>
                  <FormSection
                    title="Ranking de Ofertas"
                    description="Compare eficiencia por servico com base em CPA e ROAS."
                  >
                    <ServiceRankingTable
                      data={breakdownServicos}
                      onActionSuccess={reloadPerformance}
                      enableActions={isAdmin}
                    />
                  </FormSection>
                </Card>
              </div>
            )}
          </div>
        </Card>

        {isAdmin ? (
          <Card>
            <FormSection
              title="Ações Rápidas"
              description="Inicie um novo fluxo de criação de campanha para geração STAG, assets e publicação."
            >
              <Button variant="primary" onClick={() => navigate("/admin/campanhas/nova")}>
                Criar Nova Campanha
              </Button>
            </FormSection>
          </Card>
        ) : null}

        {isAdmin ? (
          <Card>
            <FormSection
              title="Campanhas e Relatorios"
              description="Envie o resumo de performance em PDF para o grupo do cliente no WhatsApp."
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {campanhas.map((campanha) => (
                  <div
                    key={campanha.id}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                  >
                    <p className="text-sm font-semibold text-slate-900">
                      #{campanha.id} - {campanha.cliente_nome}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {campanha.plataforma} | {campanha.status}
                    </p>
                    <div className="mt-3">
                      <Button
                        variant="primary"
                        size="sm"
                        className="bg-green-600 hover:bg-green-700 focus-visible:ring-green-500"
                        isLoading={!!sendingPorCampanha[campanha.id]}
                        onClick={() => handleEnviarGrupo(campanha.id)}
                      >
                        WhatsApp Enviar no Grupo
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </FormSection>
          </Card>
        ) : null}
      </div>

      {isAdmin && isVendaModalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <Card className="w-full max-w-md">
            <form onSubmit={handleRegistrarVenda} className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Registrar Venda</h2>
                <p className="text-sm text-slate-500">
                  Vincule o faturamento real a campanha de origem para atualizar o ROAS.
                </p>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Campanha de Origem</label>
                <select
                  value={vendaForm.campanha_id}
                  onChange={(e) => setVendaForm((prev) => ({ ...prev, campanha_id: e.target.value }))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Selecione uma campanha</option>
                  {campanhas.map((campanha) => (
                    <option key={campanha.id} value={campanha.id}>
                      #{campanha.id} - {campanha.cliente_nome} ({campanha.plataforma})
                    </option>
                  ))}
                </select>
              </div>

              <Input
                type="number"
                min={0}
                step="0.01"
                label="Valor da Venda (R$)"
                value={vendaForm.valor}
                onChange={(e) => setVendaForm((prev) => ({ ...prev, valor: e.target.value }))}
                placeholder="Ex: 500.00"
              />

              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setIsVendaModalOpen(false)}
                  disabled={isRegistering}
                >
                  Cancelar
                </Button>
                <Button type="submit" variant="primary" isLoading={isRegistering}>
                  Salvar Venda
                </Button>
              </div>
            </form>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
