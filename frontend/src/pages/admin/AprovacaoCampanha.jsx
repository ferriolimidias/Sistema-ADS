import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import { CampaignSkeleton } from "../../components/ui/Skeleton";
import StatusBadge from "../../components/ui/StatusBadge";
import Textarea from "../../components/ui/Textarea";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function AprovacaoCampanha() {
  const { campanha_id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [campaign, setCampaign] = useState(null);
  const [copyEditavel, setCopyEditavel] = useState({ grupos_anuncios: [] });
  const [raioGeografico, setRaioGeografico] = useState(10);
  const [midias, setMidias] = useState([]);
  const [uploadingPorServico, setUploadingPorServico] = useState({});

  const grupos = copyEditavel?.grupos_anuncios || [];

  async function fetchCampaign() {
    const response = await authFetch(`${API_BASE_URL}/admin/campanhas/${campanha_id}`);
    if (!response.ok) throw new Error("Falha ao carregar campanha.");
    const data = await response.json();

    setCampaign(data);
    setRaioGeografico(data.raio_geografico ?? 10);
    setCopyEditavel(data.copy_gerada || { grupos_anuncios: [] });
  }

  async function fetchMidias() {
    const response = await fetch(`${API_BASE_URL}/media/${campanha_id}`);
    if (!response.ok) throw new Error("Falha ao carregar midias.");
    const data = await response.json();
    setMidias(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setIsLoading(true);
        await Promise.all([fetchCampaign(), fetchMidias()]);
      } catch (err) {
        console.error(err);
        if (mounted) toast.error("Erro ao carregar dados da campanha.");
      } finally {
        if (mounted) setIsLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [campanha_id]);

  const midiasPorServico = useMemo(() => {
    return midias.reduce((acc, item) => {
      const key = (item.nome_servico || "__geral__").toLowerCase().trim();
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    }, {});
  }, [midias]);

  function updateItemTexto(grupoIndex, field, itemIndex, value) {
    setCopyEditavel((prev) => {
      const next = { ...(prev || {}), grupos_anuncios: [...(prev?.grupos_anuncios || [])] };
      const grupo = { ...next.grupos_anuncios[grupoIndex] };
      const arr = [...(grupo[field] || [])];
      arr[itemIndex] = value;
      grupo[field] = arr;
      next.grupos_anuncios[grupoIndex] = grupo;
      return next;
    });
  }

  async function handleUpload(servico, file) {
    if (!file) return;
    const key = servico.toLowerCase().trim();
    try {
      setUploadingPorServico((prev) => ({ ...prev, [key]: true }));

      const formData = new FormData();
      formData.append("arquivo", file);
      formData.append("nome_servico", servico);

      const response = await fetch(`${API_BASE_URL}/media/upload/${campanha_id}`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("Falha no upload de imagem.");
      await fetchMidias();
      toast.success("Upload de imagem concluído com sucesso.");
    } catch (err) {
      console.error(err);
      toast.error("Falha no upload da mídia.");
    } finally {
      setUploadingPorServico((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function handleSalvarRascunho() {
    try {
      setIsSaving(true);
      const response = await authFetch(`${API_BASE_URL}/admin/campanhas/${campanha_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          copy_gerada: copyEditavel,
          raio_geografico: Number(raioGeografico),
        }),
      });
      if (!response.ok) throw new Error("Falha ao salvar rascunho.");
      const updated = await response.json();
      setCampaign(updated);
      toast.success("Rascunho salvo com sucesso.");
    } catch (err) {
      console.error(err);
      toast.error("Erro ao salvar rascunho.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAprovarPublicar() {
    try {
      setIsApproving(true);
      const response = await authFetch(`${API_BASE_URL}/admin/campanhas/${campanha_id}/aprovar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          copy_gerada: copyEditavel,
          raio_geografico: Number(raioGeografico),
        }),
      });
      if (!response.ok) throw new Error("Falha ao aprovar campanha.");

      toast.success("Campanha aprovada e enviada para o Google Ads!");
      navigate("/admin/dashboard");
    } catch (err) {
      console.error(err);
      toast.error("Erro ao aprovar/publicar campanha.");
    } finally {
      setIsApproving(false);
    }
  }

  if (isLoading) {
    return <CampaignSkeleton />;
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card>
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Aprovacao da Campanha #{campaign?.id}</h1>
              <p className="text-sm text-slate-500">
                Revise os grupos STAG, ajuste os textos e envie imagens por servico.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={campaign?.status} />
              <span className="text-xs text-slate-500">({campaign?.plataforma || "GOOGLE"})</span>
            </div>
          </div>

          <FormSection title="Configurações da Campanha" description="Defina parâmetros globais para publicação.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Input
                type="number"
                min={0}
                label="Raio (KM)"
                value={raioGeografico}
                onChange={(e) => setRaioGeografico(e.target.value)}
              />
            </div>
          </FormSection>
        </Card>

        <section className="space-y-4">
          {grupos.map((grupo, grupoIndex) => {
            const nomeServico = grupo.nome_servico || `Servico ${grupoIndex + 1}`;
            const keyServico = nomeServico.toLowerCase().trim();
            const previewUrl = `/oferta/${campanha_id}/${slugify(nomeServico)}`;
            const imagensServico = [
              ...(midiasPorServico[keyServico] || []),
              ...(midiasPorServico["__geral__"] || []),
            ];

            return (
              <Card key={`${nomeServico}-${grupoIndex}`}>
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-slate-900">{nomeServico}</h2>
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline"
                  >
                    Preview da Landing Page
                  </a>
                </div>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Headlines</h3>
                    {(grupo.headlines || []).map((headline, idx) => (
                      <Textarea
                        key={idx}
                        label={`Headline ${idx + 1}`}
                        rows={2}
                        value={headline}
                        onChange={(e) => updateItemTexto(grupoIndex, "headlines", idx, e.target.value)}
                      />
                    ))}
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Descriptions</h3>
                    {(grupo.descriptions || []).map((description, idx) => (
                      <Textarea
                        key={idx}
                        label={`Description ${idx + 1}`}
                        value={description}
                        onChange={(e) => updateItemTexto(grupoIndex, "descriptions", idx, e.target.value)}
                        rows={2}
                      />
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
                    Palavras-chave
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {(grupo.palavras_chave || []).map((keyword, idx) => (
                      <span
                        key={`${keyword}-${idx}`}
                        className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                      Imagens do Servico
                    </h3>
                    <label className="cursor-pointer rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700">
                      {uploadingPorServico[keyServico] ? "Enviando..." : "Upload Imagem"}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => handleUpload(nomeServico, e.target.files?.[0])}
                        disabled={!!uploadingPorServico[keyServico]}
                      />
                    </label>
                  </div>

                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {imagensServico.map((img) => (
                      <div key={img.id} className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                        <img
                          src={`${API_BASE_URL}/${img.caminho_arquivo}`}
                          alt={img.nome_arquivo}
                          className="h-28 w-full object-cover"
                        />
                        <p className="truncate px-2 py-1 text-[11px] text-slate-600">{img.nome_servico || "geral"}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            );
          })}
        </section>

        <footer className="sticky bottom-0 flex flex-wrap gap-3 border-t border-slate-200 bg-slate-50 py-4">
          <Button
            onClick={handleSalvarRascunho}
            variant="outline"
            size="md"
            isLoading={isSaving}
            disabled={isApproving}
          >
            Salvar Rascunho
          </Button>
          <Button
            onClick={handleAprovarPublicar}
            variant="primary"
            size="md"
            isLoading={isApproving}
            disabled={isSaving}
            className="bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500"
          >
            Aprovar e Publicar no Google
          </Button>
        </footer>
      </div>
    </div>
  );
}
