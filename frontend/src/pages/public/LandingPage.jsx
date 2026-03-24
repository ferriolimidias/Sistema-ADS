import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function LandingPage() {
  const { campanha_id, nome_servico } = useParams();
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const rawTerm = searchParams.get("utm_term");

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        setError("");
        const response = await fetch(
          `${API_BASE_URL}/lp/${campanha_id}/${encodeURIComponent(nome_servico || "")}`,
        );
        if (!response.ok) throw new Error("Falha ao carregar oferta.");
        const payload = await response.json();
        if (mounted) setData(payload);
      } catch (err) {
        console.error(err);
        if (mounted) setError("Nao foi possivel carregar esta oferta no momento.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [campanha_id, nome_servico]);

  const mapsSrc = useMemo(() => {
    if (!data?.endereco_negocio) return "";
    return `https://www.google.com/maps?q=${encodeURIComponent(data.endereco_negocio)}&output=embed`;
  }, [data?.endereco_negocio]);
  const formattedTerm = useMemo(() => {
    if (!rawTerm) return "";
    const normalized = String(rawTerm).replace(/[+\-_]+/g, " ").trim().toLowerCase();
    if (!normalized) return "";
    return normalized
      .split(/\s+/)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }, [rawTerm]);
  const whatsappLink = data?.whatsapp_link || "#";

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        <div className="mx-auto max-w-4xl animate-pulse space-y-4">
          <div className="h-10 rounded bg-slate-200" />
          <div className="h-72 rounded bg-slate-200" />
          <div className="h-20 rounded bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <p className="text-sm text-slate-600">{error || "Oferta indisponivel."}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <main className="mx-auto max-w-4xl space-y-8 px-4 py-10">
        <section className="space-y-3 text-center">
          {/* Teste local: http://localhost:5173/lp/ID_DA_LP?utm_term=Teste+De+Mensagem */}
          {formattedTerm && (
            <div
              className="mb-6 inline-block rounded-full px-4 py-2 text-sm font-semibold animate-fade-in-down"
              style={{
                backgroundColor: `${(data?.tema?.cor_primaria || "#10b981")}20`,
                color: data?.tema?.cor_primaria || "#10b981",
                border: `1px solid ${(data?.tema?.cor_primaria || "#10b981")}40`,
              }}
            >
              ✨ Você buscou por: <span className="font-bold">"{formattedTerm}"</span>
            </div>
          )}
          <h1 className="text-3xl font-extrabold leading-tight md:text-4xl">{data.titulo_oferta}</h1>
          <p className="text-sm text-slate-500">Oferta exclusiva para atendimento rapido e local.</p>
        </section>

        <section className="space-y-4">
          {data.url_imagem ? (
            <img
              src={`${API_BASE_URL}${data.url_imagem}`}
              alt={data.titulo_oferta}
              className="mx-auto w-full max-w-2xl rounded-2xl border border-slate-200 object-cover shadow-sm"
            />
          ) : (
            <div className="mx-auto flex h-64 w-full max-w-2xl items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 text-slate-500">
              Imagem da oferta indisponivel
            </div>
          )}

          <div className="flex justify-center">
            <a
              href={whatsappLink}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
            >
              Falar com Atendimento
            </a>
          </div>
        </section>

        <section className="mx-auto max-w-2xl space-y-4 text-center">
          <p className="text-base leading-relaxed text-slate-700">{data.texto_vendas}</p>
          <div className="flex justify-center">
            <a
              id="contato"
              href={whatsappLink}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
            >
              Falar com Atendimento
            </a>
          </div>
        </section>

        {mapsSrc ? (
          <section className="overflow-hidden rounded-2xl border border-slate-200">
            <iframe
              title="Mapa da empresa"
              src={mapsSrc}
              className="h-80 w-full"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </section>
        ) : null}
      </main>

      <footer className="bg-slate-900 px-4 py-6 text-center text-sm text-slate-200">
        <p>{data.razao_social || data.nome_cliente}</p>
        <p>CNPJ: {data.cnpj || "Nao informado"}</p>
        <p>{data.endereco_negocio || "Endereco nao informado"}</p>
      </footer>
    </div>
  );
}
