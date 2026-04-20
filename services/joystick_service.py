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
    """Sistema de cálculo de pontuação para Poomsae com suporte a 2 atletas (Chong e Hong)"""
    luta_id: str
    numero_juizes: int  # 3, 5, ou 7
    
    # Rastrear notas por atleta: {"vermelho": {juiz1: 8.5, juiz2: 8.3}, "azul": {...}}
    notas_por_atleta: Dict[str, Dict[str, float]] = field(default_factory=lambda: {"vermelho": {}, "azul": {}})
    
    # Notas finais calculadas
    nota_final_vermelho: Optional[float] = None
    nota_final_azul: Optional[float] = None
    
    tempo_inicio: datetime = field(default_factory=datetime.utcnow)
    timeout_segundos: int = 120  # Tempo máximo para todos enviarem (2 min por atleta)
    
    def registrar_nota(self, juiz_email: str, nota: float, atleta: str = "vermelho") -> dict:
        """
        Registra nota de um juiz para um atleta específico.
        Retorna status e resultado se completo.
        """
        if not 0 <= nota <= 10:
            raise ValueError("Nota deve estar entre 0 e 10")
        
        if atleta not in ["vermelho", "azul"]:
            raise ValueError("Atleta deve ser 'vermelho' ou 'azul'")
        
        if juiz_email in self.notas_por_atleta[atleta]:
            raise ValueError(f"Juiz {juiz_email} já enviou nota para {atleta}")
        
        self.notas_por_atleta[atleta][juiz_email] = nota
        
        # Verificar se todos os juízes votaram para este atleta
        votos_atleta = len(self.notas_por_atleta[atleta])
        completo_atleta = votos_atleta == self.numero_juizes
        
        # Verificar se ambos os atletas têm todas as notas
        completo_ambos = (
            len(self.notas_por_atleta["vermelho"]) == self.numero_juizes and
            len(self.notas_por_atleta["azul"]) == self.numero_juizes
        )
        
        return {
            "atleta": atleta,
            "juiz": juiz_email,
            "nota_registrada": nota,
            "votos_para_atleta": votos_atleta,
            "votos_esperados": self.numero_juizes,
            "completo_atleta": completo_atleta,
            "completo_ambos": completo_ambos
        }
    
    def todas_notas_recebidas(self) -> bool:
        """Verifica se todos os juízes enviaram notas para AMBOS atletas"""
        return (
            len(self.notas_por_atleta["vermelho"]) == self.numero_juizes and
            len(self.notas_por_atleta["azul"]) == self.numero_juizes
        )
    
    def tempo_expirou(self) -> bool:
        """Verifica se o tempo limite foi ultrapassado"""
        decorrido = (datetime.utcnow() - self.tempo_inicio).total_seconds()
        return decorrido > self.timeout_segundos
    
    def calcular_nota_final(self, atleta: str) -> Optional[float]:
        """
        Calcula a nota final descartando maior e menor nota.
        Retorna a média aritmética das notas restantes.
        """
        if not self.todas_notas_recebidas():
            return None
        
        notas = list(self.notas_por_atleta[atleta].values())
        
        if len(notas) < 1:
            return None
        
        if len(notas) == 1:
            # Com 1 juiz, não descarta nada
            return round(notas[0], 2)
        
        if len(notas) == 2:
            # Com 2 juízes, não descarta nada (faz a média simples)
            media = statistics.mean(notas)
            return round(media, 2)
        
        # Com 3+: Descartar nota mais alta e mais baixa
        notas_ordenadas = sorted(notas)
        notas_validas = notas_ordenadas[1:-1]  # Remove primeira e última
        
        if not notas_validas:
            return None
        
        media = statistics.mean(notas_validas)
        return round(media, 2)
    
    def computar_notas_finais(self) -> bool:
        """Computa as notas finais para ambos atletas"""
        if not self.todas_notas_recebidas():
            return False
        
        self.nota_final_vermelho = self.calcular_nota_final("vermelho")
        self.nota_final_azul = self.calcular_nota_final("azul")
        
        return True
    
    def gerar_relatorio(self) -> dict:
        """Gera relatório completo da pontuação"""
        if not self.todas_notas_recebidas():
            return {
                "status": "incompleto",
                "notas_vermelho": len(self.notas_por_atleta["vermelho"]),
                "notas_azul": len(self.notas_por_atleta["azul"]),
                "notas_esperadas": self.numero_juizes
            }
        
        # Computar se não foi feito ainda
        if self.nota_final_vermelho is None or self.nota_final_azul is None:
            self.computar_notas_finais()
        
        notas_verm = list(self.notas_por_atleta["vermelho"].values())
        notas_azul = list(self.notas_por_atleta["azul"].values())
        
        vencedor = None
        if self.nota_final_vermelho > self.nota_final_azul:
            vencedor = "vermelho"
        elif self.nota_final_azul > self.nota_final_vermelho:
            vencedor = "azul"
        else:
            vencedor = "empate"
        
        return {
            "status": "completo",
            "notas_vermelho": self.notas_por_atleta["vermelho"],
            "notas_azul": self.notas_por_atleta["azul"],
            "nota_final_vermelho": self.nota_final_vermelho,
            "nota_final_azul": self.nota_final_azul,
            "vencedor": vencedor,
            "detalhes": {
                "vermelho": {
                    "minima": min(notas_verm) if notas_verm else None,
                    "maxima": max(notas_verm) if notas_verm else None,
                    "total_notas": len(notas_verm)
                },
                "azul": {
                    "minima": min(notas_azul) if notas_azul else None,
                    "maxima": max(notas_azul) if notas_azul else None,
                    "total_notas": len(notas_azul)
                }
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
        
        Args:
            luta_id: ID da luta
            juiz_email: Email do juiz
            nota: Nota (0-10)
            atleta: "vermelho" (Chong) ou "azul" (Hong)
            
        Retorna:
            status e resultado final se completo para ambos atletas
        """
        if luta_id not in self.poomsaes_ativas:
            raise ValueError(f"Sessão de Poomsae não encontrada para luta {luta_id}")
        
        sessao = self.poomsaes_ativas[luta_id]
        
        if sessao.tempo_expirou():
            raise ValueError("Tempo limite para envio de notas foi ultrapassado")
        
        # Registrar nota
        resultado_registro = sessao.registrar_nota(juiz_email, nota, atleta)
        
        response = {
            "luta_id": luta_id,
            "juiz_email": juiz_email,
            "atleta": atleta,
            "nota_registrada": nota,
            "votos_para_atleta": resultado_registro["votos_para_atleta"],
            "votos_esperados": sessao.numero_juizes,
            "status": "em_espera"
        }
        
        # Se todas as notas foram recebidas para AMBOS atletas, calcular resultado
        if resultado_registro["completo_ambos"]:
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
