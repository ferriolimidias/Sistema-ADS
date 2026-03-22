from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.database import Base


class FerrioliConfig(Base):
    __tablename__ = "Ferrioli_Config"

    id = Column(Integer, primary_key=True, index=True)
    meta_bm_token = Column(String, nullable=False)
    google_mcc_token = Column(String, nullable=False)
    google_ads_client_id = Column(String, nullable=True)
    google_ads_client_secret = Column(String, nullable=True)
    google_ads_refresh_token = Column(String, nullable=True)
    google_ads_use_client_customer_id = Column(String, nullable=True)
    openai_api_key = Column(String, nullable=False)


class Cliente(Base):
    __tablename__ = "Clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    cnpj = Column(String, nullable=False, unique=True, index=True)
    google_customer_id = Column(String, nullable=True)
    meta_ad_account_id = Column(String, nullable=True)
    status_ativo = Column(Boolean, default=True, nullable=False)

    campanhas = relationship("Campanha", back_populates="cliente", cascade="all, delete-orphan")
    conversoes_agenteso = relationship(
        "ConversaoAgenteSO",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )


class Campanha(Base):
    __tablename__ = "Campanhas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("Clientes.id"), nullable=False, index=True)
    id_plataforma = Column(String, nullable=False)
    plataforma = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    status = Column(String, nullable=False)
    orcamento_diario = Column(Float, nullable=False)
    roas_alvo = Column(Float, nullable=True)
    cpa_alvo = Column(Float, nullable=True)
    meta_pixel_id = Column(String, nullable=True)
    google_conversion_action_id = Column(String, nullable=True)
    plataforma_campanha_id = Column(String, nullable=True)
    copy_gerada = Column(JSON, nullable=True)

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
