"""
Serviço de geração de cronograma
"""
from datetime import datetime, timedelta


def calcular_duracao_luta(modalidade: str, eh_preta: bool, eh_adulto: bool) -> int:
    """
    Calcula a duração de uma luta/apresentação em minutos
    
    Args:
        modalidade: "Kyorugui" ou "Poomsae"
        eh_preta: Se é categoria de Faixa Preta
        eh_adulto: Se é categoria Adulto/Sub-21
        
    Returns:
        Duração em minutos
    """
    if modalidade == "Kyorugui":
        if eh_adulto and eh_preta:
            return 10  # Adulto Preta: 10 minutos de luta + intervalo
        elif eh_preta:
            return 9   # Faixa Preta: 9 minutos
        else:
            return 8   # Demais: 8 minutos
    else:  # Poomsae
        return 8 if eh_preta else 7


def distribuir_cronograma(lutas: list, num_quadras: int, horario_inicio: str, isolar_poomsae: bool = False) -> list:
    """
    Distribui as lutas nas quadras com balanceamento de tempo
    
    Args:
        lutas: Lista de lutas/apresentações a escalar
        num_quadras: Número de quadras disponíveis
        horario_inicio: Horário de início no formato "HH:MM"
        isolar_poomsae: Se True, dedica primeira quadra para Poomsae
        
    Returns:
        Lista de lutas com atribuição de quadra e horário
    """
    # Inicializa as quadras
    quadras = []
    hora_dt = datetime.strptime(horario_inicio, "%H:%M")
    
    for i in range(num_quadras):
        tipo = "Poomsae" if (isolar_poomsae and i == 0) else "Kyorugui" if (isolar_poomsae and i > 0) else "Mista"
        quadras.append({
            "id": i + 1,
            "tipo": tipo,
            "tempo_atual": hora_dt
        })
    
    # Ordena as lutas: Kyorugui primeiro, depois Poomsae
    lutas_ordenadas = sorted(lutas, key=lambda x: (x.get("modalidade") == "Poomsae", x.get("categoria_id", "")))
    
    # Distribui nas quadras
    for i, luta in enumerate(lutas_ordenadas):
        # Encontra quadra compatível com menor tempo
        quadras_compat = [q for q in quadras if q["tipo"] == "Mista" or q["tipo"] == luta.get("modalidade", "Kyorugui")]
        
        if not quadras_compat:
            quadras_compat = quadras
        
        quadra_min = min(quadras_compat, key=lambda q: q["tempo_atual"])
        
        luta["quadra"] = quadra_min["id"]
        luta["horario_previsto"] = quadra_min["tempo_atual"].strftime("%H:%M")
        luta["ordem_luta"] = i + 1
        
        # Avança o tempo dessa quadra
        duracao = luta.get("duracao_min", 8)
        quadra_min["tempo_atual"] += timedelta(minutes=duracao)
    
    return lutas_ordenadas


def estimar_tempo_total(lutas: list) -> timedelta:
    """
    Estima o tempo total do evento
    
    Args:
        lutas: Lista de lutas já escaladas com quadra
        
    Returns:
        timedelta com a duração estimada
    """
    if not lutas:
        return timedelta(0)
    
    # Agrupa por quadra e soma o tempo
    tempo_por_quadra = {}
    for luta in lutas:
        quadra = luta.get("quadra", 1)
        duracao = luta.get("duracao_min", 8)
        tempo_por_quadra[quadra] = tempo_por_quadra.get(quadra, 0) + duracao
    
    # O tempo total é o da quadra com maior tempo
    tempo_max = max(tempo_por_quadra.values()) if tempo_por_quadra else 0
    
    return timedelta(minutes=tempo_max)
