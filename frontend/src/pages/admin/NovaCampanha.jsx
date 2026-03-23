import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import FormSection from "../../components/ui/FormSection";
import Input from "../../components/ui/Input";
import Textarea from "../../components/ui/Textarea";
import { useToast } from "../../components/ui/ToastProvider";
import { authFetch } from "../../lib/auth";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function NovaCampanha() {
  const navigate = useNavigate();
  const toast = useToast();

  const [formData, setFormData] = useState({
    plataforma: "GOOGLE",
    nome_cliente: "",
    url_site: "",
    endereco_negocio: "",
    raio_geografico: 10,
    orcamento_diario: "",
    descricao_servicos: "",
  });
  const [formErrors, setFormErrors] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);

  function updateField(field, value) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    let errors = {};

    if (!String(formData.nome_cliente || "").trim()) {
      errors.nome_cliente = "O nome do cliente é obrigatório.";
    }
    if (!String(formData.endereco_negocio || "").trim()) {
      errors.endereco_negocio = "O endereço é obrigatório para campanhas locais.";
    }
    if (!formData.raio_geografico || Number(formData.raio_geografico) <= 0) {
      errors.raio_geografico = "Informe um raio válido em KM.";
    }
    if (!formData.orcamento_diario || Number(formData.orcamento_diario) < 5) {
      errors.orcamento_diario = "Orçamento diário deve ser maior que R$ 5,00.";
    }
    if (String(formData.descricao_servicos || "").trim().length < 15) {
      errors.descricao_servicos = "Descreva os serviços com mais detalhes para a IA (mín. 15 caracteres).";
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      toast.error("Corrija os campos destacados antes de gerar a campanha.");
      return;
    }

    setFormErrors({});

    try {
      setIsGenerating(true);
      const response = await authFetch(`${API_BASE_URL}/builder/gerar-ativos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!response.ok) throw new Error("Falha ao gerar campanha.");
      const payload = await response.json();
      const campanhaId = payload?.campanha_id;
      if (!campanhaId) throw new Error("Resposta sem campanha_id.");

      toast.success("Campanha gerada com sucesso!");
      navigate(`/admin/campanhas/${campanhaId}/aprovacao`);
    } catch (error) {
      console.error(error);
      toast.error("Erro ao gerar campanha com IA.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl">
        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Nova Campanha</h1>
              <p className="mt-1 text-sm text-slate-500">
                Defina os dados do negócio para a IA gerar a estrutura STAG e configuração local.
              </p>
            </div>

            <FormSection
              title="Dados do Cliente & Negócio Local"
              description="Essas informações ajudam a IA a segmentar corretamente os grupos e a geolocalização."
            >
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-slate-700">Plataforma Alvo</label>
                  <select
                    value={formData.plataforma}
                    onChange={(e) => updateField("plataforma", e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="GOOGLE">Google Ads</option>
                    <option value="META">Meta Ads</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input
                  label="Nome do Cliente"
                  value={formData.nome_cliente}
                  onChange={(e) => updateField("nome_cliente", e.target.value)}
                  placeholder="Ex: Oficina Auto Center Caxias"
                  error={formErrors.nome_cliente}
                  required
                />
                <Input
                  label="URL do Site (opcional)"
                  value={formData.url_site}
                  onChange={(e) => updateField("url_site", e.target.value)}
                  placeholder="https://www.seusite.com.br"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input
                  label="Endereço do Negócio"
                  value={formData.endereco_negocio}
                  onChange={(e) => updateField("endereco_negocio", e.target.value)}
                  placeholder="Rua Exemplo, 123 - Centro, Caxias do Sul"
                  error={formErrors.endereco_negocio}
                  required
                />
                <Input
                  type="number"
                  min={0}
                  label="Raio de Atuação (KM)"
                  value={formData.raio_geografico}
                  onChange={(e) => updateField("raio_geografico", Number(e.target.value))}
                  error={formErrors.raio_geografico}
                  required
                />
              </div>
            </FormSection>

            <FormSection
              title="Estratégia e Orçamento"
              description="Descreva os serviços para a IA separar os Ad Groups STAG e gerar os anúncios."
            >
              <Input
                type="number"
                min={0}
                step="0.01"
                label="Orçamento Diário (R$)"
                value={formData.orcamento_diario}
                onChange={(e) => updateField("orcamento_diario", e.target.value)}
                placeholder="Ex: 120.00"
                error={formErrors.orcamento_diario}
                required
              />

              <Textarea
                label="Descrição dos Serviços"
                value={formData.descricao_servicos}
                onChange={(e) => updateField("descricao_servicos", e.target.value)}
                rows={6}
                placeholder="Ex: Clínica odontológica com foco em implantes, clareamento e aparelhos."
                error={formErrors.descricao_servicos}
                required
              />
            </FormSection>

            <div className="pt-2">
              <Button type="submit" variant="primary" isLoading={isGenerating}>
                Gerar Estrutura da Campanha com IA
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
