from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from models.database import Base


class FerrioliConfig(Base):
    __tablename__ = "Ferrioli_Config"

    id = Column(Integer, primary_key=True, index=True)
    meta_bm_token = Column(String, nullable=False)
    meta_page_id = Column(String, nullable=True)
    google_mcc_token = Column(String, nullable=False)
    google_ads_client_id = Column(String, nullable=True)
    google_ads_client_secret = Column(String, nullable=True)
    google_ads_refresh_token = Column(String, nullable=True)
    google_ads_use_client_customer_id = Column(String, nullable=True)
    Maps_api_key = Column(String, nullable=True)
    evolution_api_url = Column(String, nullable=True)
    evolution_api_key = Column(String, nullable=True)
    evolution_instance_name = Column(String, nullable=True)
    openai_api_key = Column(String, nullable=False)


class Cliente(Base):
    __tablename__ = "Clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    razao_social = Column(String, nullable=True)
    cnpj = Column(String, nullable=True, unique=True, index=True)
    whatsapp = Column(String, nullable=True)
    whatsapp_group_jid = Column(String, nullable=True)
    google_customer_id = Column(String, nullable=True)
    meta_ad_account_id = Column(String, nullable=True)
    status_ativo = Column(Boolean, default=True, nullable=False)

    campanhas = relationship("Campanha", back_populates="cliente", cascade="all, delete-orphan")
    usuario = relationship("Usuario", back_populates="cliente", uselist=False)
    conversoes_agenteso = relationship(
        "ConversaoAgenteSO",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )


class UsuarioRole(str, PyEnum):
    ADMIN = "ADMIN"
    CLIENTE = "CLIENTE"


class Usuario(Base):
    __tablename__ = "Usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SqlEnum(UsuarioRole, name="usuario_role"), nullable=False, default=UsuarioRole.CLIENTE)
    needs_password_change = Column(Boolean, default=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("Clientes.id"), nullable=True, index=True)

    cliente = relationship("Cliente", back_populates="usuario")
    audit_logs = relationship("AuditLog", back_populates="usuario", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Usuarios.id"), nullable=True, index=True)
    acao = Column(String, nullable=False, index=True)
    recurso = Column(String, nullable=False)
    detalhes = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    usuario = relationship("Usuario", back_populates="audit_logs")


class Campanha(Base):
    __tablename__ = "Campanhas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("Clientes.id"), nullable=False, index=True)
    id_plataforma = Column(String, nullable=False)
    plataforma = Column(String, default="GOOGLE", nullable=False)
    tipo = Column(String, nullable=False)
    status = Column(String, nullable=False)
    orcamento_diario = Column(Float, nullable=False)
    roas_alvo = Column(Float, nullable=True)
    cpa_alvo = Column(Float, nullable=True)
    meta_pixel_id = Column(String, nullable=True)
    google_conversion_action_id = Column(String, nullable=True)
    plataforma_campanha_id = Column(String, nullable=True)
    copy_gerada = Column(JSON, nullable=True)
    raio_geografico = Column(Integer, nullable=True, default=10)
    endereco_negocio = Column(String, nullable=True)
    assets_adicionais = Column(JSON, nullable=True)

    cliente = relationship("Cliente", back_populates="campanhas")
    landing_pages = relationship(
        "LandingPage",
        back_populates="campanha",
        cascade="all, delete-orphan",
    )
    logs_otimizacao_geco = relationship(
        "LogOtimizacaoGECO",
        back_populates="campanha",
        cascade="all, delete-orphan",
    )
    metricas_diarias = relationship(
        "MetricasDiarias",
        back_populates="campanha",
        cascade="all, delete-orphan",
    )
    midias = relationship(
        "MidiaCampanha",
        back_populates="campanha",
        cascade="all, delete-orphan",
    )
    conversoes_vendas = relationship(
        "ConversaoVenda",
        back_populates="campanha",
        cascade="all, delete-orphan",
    )


class MetricasDiarias(Base):
    __tablename__ = "MetricasDiarias"
    __table_args__ = (
        UniqueConstraint("campanha_id", "data", "nome_servico", name="uq_metricas_campanha_data_servico"),
    )

    id = Column(Integer, primary_key=True, index=True)
    campanha_id = Column(Integer, ForeignKey("Campanhas.id"), nullable=False, index=True)
    data = Column(Date, nullable=False, default=lambda: datetime.utcnow().date(), index=True)
    nome_servico = Column(String, nullable=True, index=True)
    spend = Column(Float, nullable=False, default=0.0)
    conversoes = Column(Integer, nullable=False, default=0)
    receita = Column(Float, nullable=False, default=0.0)

    campanha = relationship("Campanha", back_populates="metricas_diarias")


class ConversaoVenda(Base):
    __tablename__ = "ConversaoVenda"

    id = Column(Integer, primary_key=True, index=True)
    campanha_id = Column(Integer, ForeignKey("Campanhas.id"), nullable=False, index=True)
    valor_venda = Column(Float, nullable=False)
    data_venda = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    canal = Column(String, nullable=False, default="WHATSAPP")

    campanha = relationship("Campanha", back_populates="conversoes_vendas")


class LandingPage(Base):
    __tablename__ = "LandingPages"

    id = Column(Integer, primary_key=True, index=True)
    campanha_id = Column(Integer, ForeignKey("Campanhas.id"), nullable=False, index=True)
    url_slug = Column(String, nullable=False, unique=True)
    html_path = Column(String, nullable=False)
    status = Column(String, nullable=False)

    campanha = relationship("Campanha", back_populates="landing_pages")


class ConversaoAgenteSO(Base):
    __tablename__ = "Conversoes_AgenteSO"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("Clientes.id"), nullable=True, index=True)
    telefone_hash = Column(String, nullable=False)
    tag_aplicada = Column(String, nullable=False)
    gclid = Column(String, nullable=True)
    fbclid = Column(String, nullable=True)
    valor_venda = Column(Float, nullable=True)
    enviada_plataforma = Column(Boolean, default=False, nullable=False)

    cliente = relationship("Cliente", back_populates="conversoes_agenteso")


class LogOtimizacaoGECO(Base):
    __tablename__ = "Log_Otimizacao_GECO"

    id = Column(Integer, primary_key=True, index=True)
    campanha_id = Column(Integer, ForeignKey("Campanhas.id"), nullable=False, index=True)
    acao_tomada = Column(String, nullable=False)
    motivo = Column(String, nullable=False)
    metricas_no_momento = Column(JSON, nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)

    campanha = relationship("Campanha", back_populates="logs_otimizacao_geco")


class MidiaCampanha(Base):
    __tablename__ = "MidiaCampanha"

    id = Column(Integer, primary_key=True, index=True)
    campanha_id = Column(Integer, ForeignKey("Campanhas.id"), nullable=False, index=True)
    nome_arquivo = Column(String, nullable=False)
    caminho_arquivo = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    nome_servico = Column(String, nullable=True)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)

    campanha = relationship("Campanha", back_populates="midias")
