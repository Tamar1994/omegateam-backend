"""
Modelos de Usuário (Pydantic)
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


# --- MODELOS DE ENTRADA (Request) ---

class DadosCadastro(BaseModel):
    nome: str
    sobrenome: str
    email: EmailStr
    cpf_passaporte: str
    senha: str
    sexo: str
    nascimento: str
    peso: float
    altura: float
    graduacao: str
    registro_federacao: str = ""
    registro_cbtkd: str = ""
    registro_kukkiwon: str = ""


class LoginData(BaseModel):
    email: EmailStr
    senha: str


class ValidacaoToken(BaseModel):
    email: EmailStr
    token: str


class AtualizarPerfilData(BaseModel):
    email: str
    nome: str
    sobrenome: str
    sexo: str
    nascimento: str
    peso: float
    altura: float
    graduacao: str
    registro_federacao: str = ""
    registro_cbtkd: str = ""
    registro_kukkiwon: str = ""
    equipe: str = ""
    estado: str = ""
    pais: str = ""


class AlterarSenhaData(BaseModel):
    email: str
    senha_atual: str
    nova_senha: str


class ExcluirContaData(BaseModel):
    email: str
    senha_confirmacao: str


class AtualizarPreferenciasData(BaseModel):
    email: str
    receber_notificacoes: bool


class UpdateRoleData(BaseModel):
    role: str  # "user", "arbitro" ou "admin"


# --- MODELOS DE SAÍDA (Response) ---

class UsuarioResponse(BaseModel):
    nome: str
    sobrenome: str
    email: str
    role: str
    cpf_passaporte: str
    sexo: str
    nascimento: str
    peso: float
    altura: float
    graduacao: str
    foto: Optional[str] = None
    equipe: str = ""
    estado: str = "SP"
    pais: str = "BRA"
