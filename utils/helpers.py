"""
Funções auxiliares e helpers gerais
"""
from datetime import datetime
from typing import Optional


def formatar_nome_completo(nome: str, sobrenome: str) -> str:
    """Formata o nome completo de um usuário"""
    return f"{nome} {sobrenome}".strip()


def formatar_categoria_display(idade_genero: str, graduacao: str, peso_ou_tipo: str) -> str:
    """Formata a categoria para exibição amigável"""
    return f"{idade_genero} | {graduacao} | {peso_ou_tipo}"


def get_timestamp_iso() -> str:
    """Retorna o timestamp atual em formato ISO"""
    return datetime.utcnow().isoformat()


def adicionar_complemento_nome(nome_base: str, complemento: Optional[str], nivel: str = "Estadual") -> str:
    """
    Adiciona um complemento ao nome (Equipe, Estado ou País)
    
    Args:
        nome_base: Nome base "João Silva"
        complemento: Valor a adicionar (equipe, estado, país)
        nivel: Nível do campeonato
        
    Returns:
        Nome formatado "João Silva (Equipe X)"
    """
    if not complemento or complemento.strip() == "":
        return nome_base
    return f"{nome_base} ({complemento})"


def eh_preta(graduacao: str) -> bool:
    """Verifica se a categoria é faixa preta"""
    return "Preta" in graduacao or "Dan" in graduacao


def eh_adulto(idade_genero: str) -> bool:
    """Verifica se é categoria adulto"""
    return "Adulto" in idade_genero or "Sub 21" in idade_genero or "Sub 30" in idade_genero
