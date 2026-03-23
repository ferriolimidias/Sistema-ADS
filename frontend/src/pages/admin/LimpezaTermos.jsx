import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import { Skeleton } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function LimpezaTermos() {
  const toast = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isNegating, setIsNegating] = useState(false);
  const [campanhas, setCampanhas] = useState([]);
  const [campanhaId, setCampanhaId] = useState("");
  const [periodoDias, setPeriodoDias] = useState(7);
  const [nomeServico, setNomeServico] = useState("");
  const [termos, setTermos] = useState([]);
  const [selectedTerms, setSelectedTerms] = useState({});
  const [insightsFinanceiros, setInsightsFinanceiros] = useState({
    desperdicio_identificado_periodo: 0,
    desperdicio_total_periodo: 0,
    economia_potencial_mensal: 0,
    indice_pureza_trafego: 0,
    tendencia_desperdicio_30_dias: [],
  });

  async function carregarCampanhas() {
    const response = await authFetch(`${API_BASE_URL}/admin/campanhas`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar campanhas.");
    const google = (Array.isArray(payload) ? payload : []).filter(
      (item) => String(item?.plataforma || "").toUpperCase() === "GOOGLE"
    );
    setCampanhas(google);
    if (!campanhaId && google[0]?.id) {
      setCampanhaId(String(google[0].id));
    }
  }

  async function carregarTermos() {
    if (!campanhaId) return;
    const response = await authFetch(
      `${API_BASE_URL}/admin/termos-busca?campanha_id=${encodeURIComponent(
        campanhaId
      )}&periodo_dias=${encodeURIComponent(periodoDias)}`
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload?.detail || "Falha ao carregar termos de busca.");
    setTermos(Array.isArray(payload?.termos) ? payload.termos : []);
    setInsightsFinanceiros({
      desperdicio_identificado_periodo: Number(payload?.desperdicio_identificado_periodo || 0),
      desperdicio_total_periodo: Number(payload?.desperdicio_total_periodo || 0),
      economia_potencial_mensal: Number(payload?.economia_potencial_mensal || 0),
      indice_pureza_trafego: Number(payload?.indice_pureza_trafego || 0),
      tendencia_desperdicio_30_dias: Array.isArray(payload?.tendencia_desperdicio_30_dias)
        ? payload.tendencia_desperdicio_30_dias
        : [],
    });
    setSelectedTerms({});
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        await carregarCampanhas();
      } catch (err) {
        console.error(err);
        if (mounted) toast.error(err?.message || "Erro ao carregar tela de limpeza.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!campanhaId) return;
      try {
        await carregarTermos();
      } catch (err) {
        console.error(err);
        if (mounted) toast.error(err?.message || "Erro ao carregar termos.");
      }
    })();
    return () => {
      mounted = false;
    };
  }, [campanhaId, periodoDias]);

  const servicosDisponiveis = useMemo(() => {
    const nomes = Array.from(
      new Set(
        termos
          .map((item) => String(item?.nome_servico || "").trim())
          .filter(Boolean)
      )
    );
    return nomes.sort((a, b) => a.localeCompare(b));
  }, [termos]);

  const termosFiltrados = useMemo(() => {
    if (!nomeServico) return termos;
    return termos.filter(
      (item) => String(item?.nome_servico || "").trim().toLowerCase() === nomeServico.trim().toLowerCase()
    );
  }, [termos, nomeServico]);

  const termosSelecionados = useMemo(
    () => termosFiltrados.filter((item) => selectedTerms[`${item.ad_group_id}::${item.search_term}`]),
    [termosFiltrados, selectedTerms]
  );

  const economiaSelecionadaMensal = useMemo(() => {
    const soma = termosSelecionados.reduce((acc, item) => acc + Number(item.cost || 0), 0);
    return (soma / Number(periodoDias || 1)) * 30;
  }, [termosSelecionados, periodoDias]);

  const desperdicioSelecionadoPeriodo = useMemo(
    () => termosSelecionados.reduce((acc, item) => acc + Number(item.cost || 0), 0),
    [termosSelecionados]
  );

  const indicePurezaAtual = useMemo(() => {
    const custoTotal = termosFiltrados.reduce((acc, item) => acc + Number(item.cost || 0), 0);
    if (custoTotal <= 0) return 0;
    const custoComConversao = termosFiltrados
      .filter((item) => Number(item.conversions || 0) > 0)
      .reduce((acc, item) => acc + Number(item.cost || 0), 0);
    return (custoComConversao / custoTotal) * 100;
  }, [termosFiltrados]);

  async function handleAnalisarIA() {
    if (!campanhaId || !nomeServico) {
      toast.warning("Selecione campanha e servico para analisar.");
      return;
    }
    try {
      setIsAnalyzing(true);
      const response = await authFetch(`${API_BASE_URL}/admin/termos-busca/analisar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          campanha_id: Number(campanhaId),
          nome_servico: nomeServico,
          periodo_dias: Number(periodoDias),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail || "Falha na analise da IA.");

      const mapaSugeridos = new Set(
        (payload?.termos_negativar || []).map((item) => String(item || "").trim().toLowerCase())
      );
      const atualizados = termos.map((item) => {
        const termo = String(item?.search_term || "").trim().toLowerCase();
        const sugestao = mapaSugeridos.has(termo);
        return { ...item, sugerido_negativar: sugestao };
      });
      setTermos(atualizados);

      const selecionados = {};
      for (const item of atualizados) {
        if (item.sugerido_negativar) {
          const key = `${item.ad_group_id}::${item.search_term}`;
          selecionados[key] = true;
        }
      }
      setSelectedTerms(selecionados);
      toast.success("Analise de termos concluida.");
    } catch (err) {
      console.error(err);
      toast.error(err?.message || "Erro ao analisar termos com IA.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function toggleSelect(item) {
    const key = `${item.ad_group_id}::${item.search_term}`;
    setSelectedTerms((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleNegativarSelecionados() {
    const selecionados = termosFiltrados.filter((item) => selectedTerms[`${item.ad_group_id}::${item.search_term}`]);
    if (selecionados.length === 0) {
      toast.warning("Selecione ao menos um termo para negativar.");
      return;
    }
    if (!nomeServico) {
      toast.warning("Selecione o servico para negativar.");
      return;
    }

    const grupos = selecionados.reduce((acc, item) => {
      const adGroupId = String(item.ad_group_id || "");
      if (!adGroupId) return acc;
      if (!acc[adGroupId]) acc[adGroupId] = [];
      acc[adGroupId].push(String(item.search_term || "").trim());
      return acc;
    }, {});

    const promise = (async () => {
      setIsNegating(true);
      try {
        for (const [adGroupId, termosGrupo] of Object.entries(grupos)) {
          const response = await authFetch(`${API_BASE_URL}/admin/termos-busca/negativar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              campanha_id: Number(campanhaId),
              nome_servico: nomeServico,
              ad_group_id: adGroupId,
              termos: termosGrupo,
            }),
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload?.detail || "Falha ao negativar termos.");
        }
        await carregarTermos();
      } finally {
        setIsNegating(false);
      }
    })();

    await toast.promise(promise, {
      loading: "Negativando termos selecionados...",
      success: "Termos negativados com sucesso.",
      error: (err) => err?.message || "Erro ao negativar termos.",
    });
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="mx-auto max-w-7xl space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card>
          <FormSection
            title="Limpeza de Termos de Busca"
            description="Analise termos irrelevantes e aplique negativacao por servico (STAG)."
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">Campanha</label>
                <select
                  value={campanhaId}
                  onChange={(e) => setCampanhaId(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Selecione</option>
                  {campanhas.map((campanha) => (
                    <option key={campanha.id} value={campanha.id}>
                      #{campanha.id} - {campanha.cliente_nome}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">Periodo</label>
                <select
                  value={periodoDias}
                  onChange={(e) => setPeriodoDias(Number(e.target.value))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value={7}>Ultimos 7 dias</option>
                  <option value={14}>Ultimos 14 dias</option>
                  <option value={30}>Ultimos 30 dias</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">Servico (STAG)</label>
                <select
                  value={nomeServico}
                  onChange={(e) => setNomeServico(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Todos</option>
                  {servicosDisponiveis.map((servico) => (
                    <option key={servico} value={servico}>
                      {servico}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end gap-2">
                <Button variant="outline" onClick={carregarTermos}>
                  Atualizar Lista
                </Button>
                <Button variant="primary" isLoading={isAnalyzing} onClick={handleAnalisarIA}>
                  Analisar com IA
                </Button>
              </div>
            </div>
          </FormSection>
        </Card>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card>
            <p className="text-sm font-medium text-slate-500">Desperdicio Identificado (Periodo)</p>
            <p className="mt-2 text-2xl font-bold text-red-600">
              {formatBRL(
                desperdicioSelecionadoPeriodo > 0
                  ? desperdicioSelecionadoPeriodo
                  : insightsFinanceiros.desperdicio_identificado_periodo
              )}
            </p>
            <p className="mt-1 text-xs text-slate-500">Custos de termos sugeridos para negativacao.</p>
          </Card>
          <Card>
            <p className="text-sm font-medium text-slate-500">Economia Projetada (Mensal)</p>
            <p className="mt-2 text-2xl font-bold text-emerald-600">
              {formatBRL(
                economiaSelecionadaMensal > 0
                  ? economiaSelecionadaMensal
                  : insightsFinanceiros.economia_potencial_mensal
              )}
            </p>
            <p className="mt-1 text-xs text-slate-500">Atualiza em tempo real conforme selecao.</p>
          </Card>
          <Card>
            <p className="text-sm font-medium text-slate-500">Indice de Pureza do Trafego</p>
            <p className="mt-2 text-2xl font-bold text-slate-900">
              {(indicePurezaAtual || insightsFinanceiros.indice_pureza_trafego).toFixed(1)}%
            </p>
            <p className="mt-1 text-xs text-slate-500">Percentual de verba com potencial de conversao.</p>
          </Card>
        </div>

        <Card>
          <FormSection
            title="Tendencia de Desperdicio (30 dias)"
            description="Evolucao do custo com termos irrelevantes no ultimo mes."
          >
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={insightsFinanceiros.tendencia_desperdicio_30_dias}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="wasteGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="data" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `R$ ${Number(v || 0).toFixed(0)}`} />
                  <Tooltip
                    formatter={(value) => [formatBRL(value), "Custo"]}
                    labelFormatter={(label) => `Data: ${label}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="custo"
                    stroke="#ef4444"
                    fillOpacity={1}
                    fill="url(#wasteGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </FormSection>
        </Card>

        <Card>
          <FormSection
            title="Termos Encontrados"
            description="Linhas em vermelho sao sugestoes de negativacao da IA."
          >
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Sel.</th>
                    <th className="px-4 py-3">Termo</th>
                    <th className="px-4 py-3">Servico</th>
                    <th className="px-4 py-3">Cliques</th>
                    <th className="px-4 py-3">Custo</th>
                    <th className="px-4 py-3">Conversoes</th>
                  </tr>
                </thead>
                <tbody>
                  {termosFiltrados.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        Nenhum termo encontrado para os filtros selecionados.
                      </td>
                    </tr>
                  ) : (
                    termosFiltrados.map((item, idx) => {
                      const key = `${item.ad_group_id}::${item.search_term}`;
                      const sugerido = Boolean(item.sugerido_negativar);
                      return (
                        <tr
                          key={`${key}-${idx}`}
                          className={`border-t border-slate-100 ${sugerido ? "bg-red-50" : ""}`}
                        >
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={Boolean(selectedTerms[key])}
                              onChange={() => toggleSelect(item)}
                              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-800">{item.search_term}</td>
                          <td className="px-4 py-3 text-slate-600">{item.nome_servico || "-"}</td>
                          <td className="px-4 py-3 text-slate-700">{Number(item.clicks || 0).toLocaleString("pt-BR")}</td>
                          <td className="px-4 py-3 text-slate-700">{formatBRL(item.cost || 0)}</td>
                          <td className="px-4 py-3 text-slate-700">
                            {Number(item.conversions || 0).toLocaleString("pt-BR")}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            <div className="pt-2">
              <Button
                variant="danger"
                isLoading={isNegating}
                onClick={handleNegativarSelecionados}
              >
                Negativar Selecionados
              </Button>
            </div>
          </FormSection>
        </Card>
      </div>
    </div>
  );
}
