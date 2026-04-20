"""
Serviço de Joystick para Árbitros Laterais
Implementa Janela de Coincidência (Kyorugui) e Cálculo de Poomsae
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import asyncio
import statistics


@dataclass
class CoincidenceWindow:
    """Janela de Coincidência para validação de pontos em Kyorugui"""
    luta_id: str
    total_laterais: int = 2  # Total de árbitros laterais para calcular maioria
    lateral_cliques: Dict[str, list] = field(default_factory=dict)  # {"lateral1": [clicks], "lateral2": [...]}
    tempo_inicio: datetime = field(default_factory=datetime.utcnow)
    duracao_ms: int = 1500  # 1.5 segundos - padrão Taekwondo
    
    def está_ativa(self) -> bool:
        """Verifica se a janela ainda está aberta"""
        tempo_decorrido = (datetime.utcnow() - self.tempo_inicio).total_seconds() * 1000
        return tempo_decorrido < self.duracao_ms
    
    def registrar_clique(self, lateral: str, tipo_ponto: str, cor: str):
        """Registra um clique de um árbitro lateral"""
        if lateral not in self.lateral_cliques:
            self.lateral_cliques[lateral] = []
        
        self.lateral_cliques[lateral].append({
            "tipo": tipo_ponto,  # "+1", "+2", "+3"
            "cor": cor,  # "vermelho" ou "azul"
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def validar_ponto(self) -> Optional[dict]:
        """
        Valida se há MAIORIA ABSOLUTA de votos entre árbitros (árbitros DIFERENTES).
        
        Maioria Absoluta (Mais de 50%):
        - 2 árbitros: ambos precisam votar (2 de 2 = 100%)
        - 3 árbitros: 2 precisam votar (2 de 3 = 66%)
        - 4 árbitros: 3 precisam votar (3 de 4 = 75%)
        - 5 árbitros: 3 precisam votar (3 de 5 = 60%)
        
        Cálculo: (total_laterais // 2) + 1
        """
        if not self.está_ativa():
            return None
        
        # ✅ CORREÇÃO: Maioria absoluta = mais de 50%
        # Com 2 árbitros: (2 // 2) + 1 = 2 (ambos precisam)
        # Com 3 árbitros: (3 // 2) + 1 = 2 (maioria de 3)
        votos_necessarios = (self.total_laterais // 2) + 1
        
        # Contar votos por (cor, tipo_ponto)
        votos = {}
        for lateral, cliques in self.lateral_cliques.items():
            for clique in cliques:
                chave = f"{clique['cor']}_{clique['tipo']}"
                if chave not in votos:
                    votos[chave] = {"count": 0, "arbitros": set(), "data": clique}
                # Contar como um voto único por árbitro (evita duplo clique do mesmo)
                votos[chave]["arbitros"].add(lateral)
                votos[chave]["count"] = len(votos[chave]["arbitros"])
        
        # Verificar se há maioria absoluta
        for chave, info in votos.items():
            if info["count"] >= votos_necessarios:  # Maioria confirmada
                cor, tipo = chave.split("_")
                return {
                    "cor": cor,
                    "tipo": tipo,
                    "pontos": int(tipo[1:]),  # "+2" → 2
                    "arbitros_confirmados": info["count"],
                    "validado_em": datetime.utcnow().isoformat()
                }
        
        return None


@dataclass
class PoomsaeScoring:
    """
    Sistema de cálculo de pontuação para Poomsae com 2 fases:
    
    FASE 1: ACCURACY (Precisão)
    - Base: 4.00
    - Deduções: -0.1 (simples) ou -0.3 (grave)
    - Mínimo: 0.00
    
    FASE 2: APRESENTAÇÃO (após accuracy completa)
    - 3 quesitos, cada um 0-2.00:
      - Velocidade e Força
      - Ritmo/Tempo
      - Expressão de Energia
    - Total máximo: 6.00
    
    NOTA FINAL = ACCURACY + APRESENTAÇÃO (máx 10.00)
    """
    luta_id: str
    numero_juizes: int
    
    # Rastrear ACCURACY por atleta: {"vermelho": {juiz1: 3.8, juiz2: 3.7}, "azul": {...}}
    accuracy_por_atleta: Dict[str, Dict[str, float]] = field(default_factory=lambda: {"vermelho": {}, "azul": {}})
    
    # Rastrear APRESENTAÇÃO por atleta: {"vermelho": {juiz1: {...}, juiz2: {...}}, "azul": {...}}
    # Cada apresentação tem: {velocidade: 1.5, ritmo: 1.8, expressao: 2.0}
    apresentacao_por_atleta: Dict[str, Dict[str, dict]] = field(default_factory=lambda: {"vermelho": {}, "azul": {}})
    
    # Notas finais calculadas
    notas_finais: Dict[str, float] = field(default_factory=dict)  # {"vermelho": 9.2, "azul": 8.5}
    
    tempo_inicio: datetime = field(default_factory=datetime.utcnow)
    timeout_segundos: int = 120
    
    def registrar_accuracy(self, juiz_email: str, nota: float, atleta: str = "vermelho") -> dict:
        """Registra nota de PRECISÃO de um juiz"""
        if not 0 <= nota <= 4:
            raise ValueError("Nota de Accuracy deve estar entre 0 e 4.00")
        
        if atleta not in ["vermelho", "azul"]:
            raise ValueError("Atleta deve ser 'vermelho' ou 'azul'")
        
        if juiz_email in self.accuracy_por_atleta[atleta]:
            raise ValueError(f"Juiz {juiz_email} já enviou accuracy para {atleta}")
        
        self.accuracy_por_atleta[atleta][juiz_email] = nota
        
        votos = len(self.accuracy_por_atleta[atleta])
        return {
            "atleta": atleta,
            "juiz": juiz_email,
            "nota_registrada": nota,
            "votos_para_atleta": votos,
            "votos_esperados": self.numero_juizes,
            "accuracy_completo": votos == self.numero_juizes
        }
    
    def registrar_apresentacao(self, juiz_email: str, velocidade: float, ritmo: float, 
                               expressao: float, atleta: str = "vermelho") -> dict:
        """Registra notas de APRESENTAÇÃO de um juiz (3 quesitos 0-2.00)"""
        if not (0 <= velocidade <= 2 and 0 <= ritmo <= 2 and 0 <= expressao <= 2):
            raise ValueError("Notas de Apresentação devem estar entre 0 e 2.00")
        
        if atleta not in ["vermelho", "azul"]:
            raise ValueError("Atleta deve ser 'vermelho' ou 'azul'")
        
        if juiz_email in self.apresentacao_por_atleta[atleta]:
            raise ValueError(f"Juiz {juiz_email} já enviou apresentação para {atleta}")
        
        self.apresentacao_por_atleta[atleta][juiz_email] = {
            "velocidade": velocidade,
            "ritmo": ritmo,
            "expressao": expressao,
            "total": velocidade + ritmo + expressao
        }
        
        votos = len(self.apresentacao_por_atleta[atleta])
        return {
            "atleta": atleta,
            "juiz": juiz_email,
            "velocidade": velocidade,
            "ritmo": ritmo,
            "expressao": expressao,
            "votos_para_atleta": votos,
            "votos_esperados": self.numero_juizes,
            "apresentacao_completo": votos == self.numero_juizes
        }
    
    def todas_notas_recebidas(self) -> bool:
        """Verifica se ACCURACY E APRESENTAÇÃO estão completos para AMBOS atletas"""
        return (
            len(self.accuracy_por_atleta["vermelho"]) == self.numero_juizes and
            len(self.accuracy_por_atleta["azul"]) == self.numero_juizes and
            len(self.apresentacao_por_atleta["vermelho"]) == self.numero_juizes and
            len(self.apresentacao_por_atleta["azul"]) == self.numero_juizes
        )
    
    def tempo_expirou(self) -> bool:
        """Verifica se o tempo limite foi ultrapassado"""
        decorrido = (datetime.utcnow() - self.tempo_inicio).total_seconds()
        return decorrido > self.timeout_segundos
    
    def calcular_media_por_quesito(self, quesito_values: list) -> float:
        """
        Calcula média descartando maior e menor.
        Para 1-2 juízes, não descarta. Para 3+, descarta extremos.
        """
        if len(quesito_values) == 0:
            return 0.0
        
        if len(quesito_values) == 1:
            return round(quesito_values[0], 2)
        
        if len(quesito_values) == 2:
            return round(statistics.mean(quesito_values), 2)
        
        # 3+ juízes: descartar extremos
        ordenados = sorted(quesito_values)
        validos = ordenados[1:-1]
        return round(statistics.mean(validos), 2)
    
    def computar_notas_finais(self) -> bool:
        """Computa as notas finais para ambos atletas"""
        if not self.todas_notas_recebidas():
            return False
        
        for atleta in ["vermelho", "azul"]:
            # Calcular ACCURACY média
            accuracy_values = list(self.accuracy_por_atleta[atleta].values())
            accuracy_final = self.calcular_media_por_quesito(accuracy_values)
            
            # Calcular APRESENTAÇÃO média (por quesito)
            apresentacao_values = list(self.apresentacao_por_atleta[atleta].values())
            
            velocidade_vals = [ap["velocidade"] for ap in apresentacao_values]
            ritmo_vals = [ap["ritmo"] for ap in apresentacao_values]
            expressao_vals = [ap["expressao"] for ap in apresentacao_values]
            
            velocidade_final = self.calcular_media_por_quesito(velocidade_vals)
            ritmo_final = self.calcular_media_por_quesito(ritmo_vals)
            expressao_final = self.calcular_media_por_quesito(expressao_vals)
            
            apresentacao_total = velocidade_final + ritmo_final + expressao_final
            
            # NOTA FINAL = ACCURACY + APRESENTAÇÃO
            nota_final = round(accuracy_final + apresentacao_total, 2)
            
            self.notas_finais[atleta] = {
                "accuracy": accuracy_final,
                "apresentacao": apresentacao_total,
                "velocidade": velocidade_final,
                "ritmo": ritmo_final,
                "expressao": expressao_final,
                "total": nota_final
            }
        
        return True
    
    def gerar_relatorio(self) -> dict:
        """Gera relatório completo"""
        if not self.todas_notas_recebidas():
            return {"status": "incompleto"}
        
        if not self.notas_finais:
            self.computar_notas_finais()
        
        nota_verm = self.notas_finais.get("vermelho", {}).get("total", 0)
        nota_azul = self.notas_finais.get("azul", {}).get("total", 0)
        
        vencedor = None
        if nota_verm > nota_azul:
            vencedor = "vermelho"
        elif nota_azul > nota_verm:
            vencedor = "azul"
        else:
            vencedor = "empate"
        
        return {
            "status": "completo",
            "nota_final_vermelho": nota_verm,
            "nota_final_azul": nota_azul,
            "notas": {
                "vermelho": self.notas_finais.get("vermelho", {}),
                "azul": self.notas_finais.get("azul", {})
            },
            "vencedor": vencedor,
            "detalhes": {
                "accuracy_vermelho": list(self.accuracy_por_atleta["vermelho"].values()),
                "accuracy_azul": list(self.accuracy_por_atleta["azul"].values()),
                "apresentacao_vermelho": list(self.apresentacao_por_atleta["vermelho"].values()),
                "apresentacao_azul": list(self.apresentacao_por_atleta["azul"].values())
            }
        }


class JoystickManager:
    """Gerenciador central de joysticks e pontuação"""
    
    def __init__(self):
        self.janelas_ativas: Dict[str, CoincidenceWindow] = {}
        self.poomsaes_ativas: Dict[str, PoomsaeScoring] = {}
        self.conexoes_laterais: Dict[str, set] = {}  # {luta_id: {lateral_email1, lateral_email2, ...}}
    
    def criar_janela_coincidencia(self, luta_id: str, total_laterais: int = 2) -> CoincidenceWindow:
        """Cria uma nova janela de coincidência para uma luta"""
        janela = CoincidenceWindow(luta_id=luta_id, total_laterais=total_laterais)
        self.janelas_ativas[luta_id] = janela
        return janela
    
    def limpar_janela_expirada(self, luta_id: str) -> Optional[dict]:
        """Remove janela expirada e retorna último resultado"""
        if luta_id not in self.janelas_ativas:
            return None
        
        janela = self.janelas_ativas[luta_id]
        if not janela.está_ativa():
            resultado = janela.validar_ponto()
            del self.janelas_ativas[luta_id]
            return resultado
        
        return None
    
    def registrar_clique_lateral(self, luta_id: str, lateral_email: str, 
                                 tipo_ponto: str, cor: str, total_laterais: int = 2) -> Optional[dict]:
        """
        Registra clique de árbitro lateral e verifica validação por MAIORIA ABSOLUTA.
        Retorna ponto validado se houver maioria absoluta de votos de árbitros DIFERENTES.
        
        Args:
            luta_id: ID da luta
            lateral_email: Email do árbitro lateral que clicou
            tipo_ponto: "+1", "+2" ou "+3"
            cor: "vermelho" ou "azul"
            total_laterais: Total de árbitros laterais para calcular maioria
        """
        # Criar janela se não existir
        if luta_id not in self.janelas_ativas:
            self.criar_janela_coincidencia(luta_id, total_laterais)
        
        janela = self.janelas_ativas[luta_id]
        
        # Se janela expirou, iniciar nova
        if not janela.está_ativa():
            self.criar_janela_coincidencia(luta_id, total_laterais)
            janela = self.janelas_ativas[luta_id]
        
        # Registrar clique
        janela.registrar_clique(lateral_email, tipo_ponto, cor)
        
        # Verificar validação por maioria absoluta
        ponto_validado = janela.validar_ponto()
        
        if ponto_validado:
            # Limpar para próximo ponto
            del self.janelas_ativas[luta_id]
        
        return ponto_validado
    
    def criar_sessao_poomsae(self, luta_id: str, numero_juizes: int = 3) -> PoomsaeScoring:
        """Cria uma nova sessão de pontuação para Poomsae"""
        sessao = PoomsaeScoring(luta_id=luta_id, numero_juizes=numero_juizes)
        self.poomsaes_ativas[luta_id] = sessao
        return sessao
    
    def registrar_nota_poomsae(self, luta_id: str, juiz_email: str, nota: float, atleta: str = "vermelho") -> dict:
        """
        Registra nota de um juiz para Poomsae (atleta específico).
        DESCONTINUADO: Use registrar_accuracy_poomsae e registrar_apresentacao_poomsae
        """
        raise NotImplementedError("Use registrar_accuracy_poomsae ou registrar_apresentacao_poomsae")
    
    def registrar_accuracy_poomsae(self, luta_id: str, juiz_email: str, nota: float, atleta: str = "vermelho") -> dict:
        """
        Registra nota de PRECISÃO (ACCURACY) de um juiz para Poomsae.
        
        Args:
            luta_id: ID da luta
            juiz_email: Email do juiz
            nota: Nota de accuracy (0-4.00)
            atleta: "vermelho" (Chong) ou "azul" (Hong)
        """
        if luta_id not in self.poomsaes_ativas:
            raise ValueError(f"Sessão de Poomsae não encontrada para luta {luta_id}")
        
        sessao = self.poomsaes_ativas[luta_id]
        
        if sessao.tempo_expirou():
            raise ValueError("Tempo limite para envio de notas foi ultrapassado")
        
        resultado = sessao.registrar_accuracy(juiz_email, nota, atleta)
        
        return {
            "tipo": "accuracy_registrada",
            "luta_id": luta_id,
            "juiz_email": juiz_email,
            "atleta": atleta,
            "nota_accuracy": nota,
            "votos_para_atleta": resultado["votos_para_atleta"],
            "votos_esperados": sessao.numero_juizes,
            "accuracy_completo": resultado["accuracy_completo"],
            "status": "accuracy_registrada"
        }
    
    def registrar_apresentacao_poomsae(self, luta_id: str, juiz_email: str, velocidade: float, 
                                       ritmo: float, expressao: float, atleta: str = "vermelho") -> dict:
        """
        Registra nota de APRESENTAÇÃO de um juiz para Poomsae.
        
        Args:
            luta_id: ID da luta
            juiz_email: Email do juiz
            velocidade: Nota de velocidade (0-2.00)
            ritmo: Nota de ritmo (0-2.00)
            expressao: Nota de expressão (0-2.00)
            atleta: "vermelho" ou "azul"
        """
        if luta_id not in self.poomsaes_ativas:
            raise ValueError(f"Sessão de Poomsae não encontrada para luta {luta_id}")
        
        sessao = self.poomsaes_ativas[luta_id]
        
        if sessao.tempo_expirou():
            raise ValueError("Tempo limite para envio de notas foi ultrapassado")
        
        resultado = sessao.registrar_apresentacao(juiz_email, velocidade, ritmo, expressao, atleta)
        
        response = {
            "tipo": "apresentacao_registrada",
            "luta_id": luta_id,
            "juiz_email": juiz_email,
            "atleta": atleta,
            "velocidade": velocidade,
            "ritmo": ritmo,
            "expressao": expressao,
            "votos_para_atleta": resultado["votos_para_atleta"],
            "votos_esperados": sessao.numero_juizes,
            "apresentacao_completo": resultado["apresentacao_completo"],
            "status": "apresentacao_registrada"
        }
        
        # Se TODAS as notas foram recebidas (accuracy + apresentação para ambos atletas)
        if sessao.todas_notas_recebidas():
            sessao.computar_notas_finais()
            response["status"] = "completo"
            response["relatorio"] = sessao.gerar_relatorio()
            
            # Limpar sessão
            del self.poomsaes_ativas[luta_id]
        
        return response
    
    def obter_status_poomsae(self, luta_id: str) -> dict:
        """Obtém status atual de uma sessão de Poomsae"""
        if luta_id not in self.poomsaes_ativas:
            return {"status": "nao_existe"}
        
        sessao = self.poomsaes_ativas[luta_id]
        
        return {
            "status": "em_progresso",
            "notas_recebidas": len(sessao.notas_recebidas),
            "notas_esperadas": sessao.numero_juizes,
            "tempo_restante_segundos": max(0, sessao.timeout_segundos - 
                                          (datetime.utcnow() - sessao.tempo_inicio).total_seconds()),
            "juizes_que_ja_votaram": list(sessao.notas_recebidas.keys())
        }


# Instância global do gerenciador
joystick_manager = JoystickManager()
