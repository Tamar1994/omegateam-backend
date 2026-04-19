"""
Serviço de geração de chaves e brackets
"""
import math


def calcular_chaves_kyorugui(num_atletas: int) -> dict:
    """
    Calcula a quantidade de lutas e distribuição para Kyorugui
    
    Args:
        num_atletas: Número de atletas inscritos
        
    Returns:
        dict com informações sobre as chaves
    """
    if num_atletas == 0:
        return {"erro": "Nenhum atleta"}
    
    # Próxima potência de 2
    next_power_of_2 = 2 ** math.ceil(math.log2(num_atletas))
    num_byes = next_power_of_2 - num_atletas
    
    num_fases = math.log2(next_power_of_2)
    num_lutas = num_atletas - 1
    
    return {
        "num_atletas": num_atletas,
        "proximo_poder_de_2": next_power_of_2,
        "num_byes": num_byes,
        "num_cabecas_de_chave": num_byes,
        "num_fases": int(num_fases),
        "total_lutas": num_lutas
    }


def gerar_pares_kyorugui(atletas: list) -> list:
    """
    Gera os pares para Kyorugui com distribuição balanceada
    
    Args:
        atletas: Lista ordenada de atletas (já deve estar por data de inscrição)
        
    Returns:
        Lista de tuplas (atleta_vermelho, atleta_azul)
    """
    N = len(atletas)
    
    if N == 1:
        return [(atletas[0], "Ouro (Sem oponente)")]
    
    # Matemática de BYEs
    next_power_of_2 = 2 ** math.ceil(math.log2(N))
    num_byes = next_power_of_2 - N
    
    cabecas_de_chave = atletas[:num_byes]
    restantes = atletas[num_byes:]
    
    pares = []
    
    # Cabeças de chave recebem BYE
    for atleta in cabecas_de_chave:
        pares.append((atleta, "BYE (Avança Direto)"))
    
    # Lutas reais
    for i in range(0, len(restantes), 2):
        if i + 1 < len(restantes):
            pares.append((restantes[i], restantes[i+1]))
        else:
            pares.append((restantes[i], "BYE (Avança Direto)"))
    
    return pares


def eh_categoria_preta(nome_categoria: str) -> bool:
    """Verifica se é uma categoria de Faixa Preta"""
    return "Preta" in nome_categoria or "Adulto Preta" in nome_categoria


def eh_categoria_adulto(nome_categoria: str) -> bool:
    """Verifica se é categoria adulto ou sub-21"""
    return "Adulto" in nome_categoria or "Sub 21" in nome_categoria
