import { useCallback, useEffect, useState } from "react";

import { authFetch } from "../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function usePerformance({ isAdmin, campanhaId = null }) {
  const [periodoDias, setPeriodoDias] = useState(7);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    gasto_total: 0,
    receita_total: 0,
    roas_geral: null,
    total_leads: 0,
    breakdown_servicos: [],
  });

  const carregarPerformance = useCallback(async () => {
    const base = isAdmin ? "/admin/performance-consolidada" : "/client/performance-consolidada";
    const campanhaQuery = campanhaId ? `&campanha_id=${encodeURIComponent(campanhaId)}` : "";
    const query = `?incluir_servicos=true&periodo_dias=${encodeURIComponent(periodoDias)}${campanhaQuery}`;
    const response = await authFetch(`${API_BASE_URL}${base}${query}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.detail || "Falha ao carregar performance consolidada.");
    }
    setData({
      gasto_total: payload?.gasto_total || 0,
      receita_total: payload?.receita_total || 0,
      roas_geral: payload?.roas_geral ?? null,
      total_leads: payload?.total_leads || 0,
      breakdown_servicos: Array.isArray(payload?.breakdown_servicos) ? payload.breakdown_servicos : [],
    });
    return payload;
  }, [isAdmin, periodoDias, campanhaId]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        setError(null);
        await carregarPerformance();
      } catch (err) {
        if (mounted) setError(err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [carregarPerformance]);

  return {
    data,
    isLoading,
    error,
    periodoDias,
    setPeriodoDias,
    reloadPerformance: carregarPerformance,
  };
}
