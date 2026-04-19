"""
Modelos de Campeonato (Pydantic)
"""
from pydantic import BaseModel
from typing import List, Optional


class CategoriaData(BaseModel):
    id: str
    modalidade: str  # "Kyorugui", "Poomsae", "Parataekwondo"
    idade_genero: str  # Ex: "Sub 11 Masc"
    graduacao: str  # Ex: "8º a 5º Gub"
    peso_ou_tipo: str  # Ex: "Até 30 kg" ou "Individual"
    pesagem: bool


class CampeonatoData(BaseModel):
    nome: str
    data_evento: str
    local: str
    modalidades: str
    inclui_parataekwondo: bool = False
    status: str = "Inscrições Abertas"
    oficio_url: str = ""
    categorias: List[CategoriaData] = []
    nivel: str = "Estadual"


class AtualizarCategoriasData(BaseModel):
    categorias: List[CategoriaData]


class ConfigCronograma(BaseModel):
    num_quadras: int = 1
    isolar_poomsae: bool = True
    horario_inicio: str = "08:30"


class EquipeQuadraData(BaseModel):
    numero_quadra: int
    mesario_email: str = ""
    central_email: str = ""
    lateral1_email: str = ""
    lateral2_email: str = ""
    lateral3_email: str = ""
    lateral4_email: str = ""
    lateral5_email: str = ""
