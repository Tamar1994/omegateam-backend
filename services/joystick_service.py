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
        Valida se há coincidência de votos entre árbitros.
        Retorna o ponto validado ou None se não houver validação.
        """
        if not self.está_ativa():
            return None
        
        # Contar votos por (cor, tipo_ponto)
        votos = {}
        for lateral, cliques in self.lateral_cliques.items():
            for clique in cliques:
                chave = f"{clique['cor']}_{clique['tipo']}"
                if chave not in votos:
                    votos[chave] = {"count": 0, "data": clique}
                votos[chave]["count"] += 1
        
        # Verificar se há coincidência (mínimo 2 árbitros votando igual)
        for chave, info in votos.items():
            if info["count"] >= 2:  # Coincidência confirmada
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
    """Sistema de cálculo de pontuação para Poomsae"""
    luta_id: str
    numero_juizes: int  # 3, 5, ou 7
    notas_recebidas: Dict[str, float] = field(default_factory=dict)  # {"juiz1": 7.5, ...}
    tempo_inicio: datetime = field(default_factory=datetime.utcnow)
    timeout_segundos: int = 60  # Tempo máximo para todos enviarem
    
    def registrar_nota(self, juiz_email: str, nota: float) -> bool:
        """Registra nota de um juiz"""
        if not 0 <= nota <= 10:
            raise ValueError("Nota deve estar entre 0 e 10")
        
        if juiz_email in self.notas_recebidas:
            raise ValueError(f"Juiz {juiz_email} já enviou sua nota")
        
        self.notas_recebidas[juiz_email] = nota
        return len(self.notas_recebidas) == self.numero_juizes
    
    def todas_notas_recebidas(self) -> bool:
        """Verifica se todos os juízes enviaram suas notas"""
        return len(self.notas_recebidas) == self.numero_juizes
    
    def tempo_expirou(self) -> bool:
        """Verifica se o tempo limite foi ultrapassado"""
        decorrido = (datetime.utcnow() - self.tempo_inicio).total_seconds()
        return decorrido > self.timeout_segundos
    
    def calcular_nota_final(self) -> Optional[float]:
        """
        Calcula a nota final descartando maior e menor nota.
        Retorna a média aritmética das notas restantes.
        """
        if not self.todas_notas_recebidas():
            return None
        
        notas = list(self.notas_recebidas.values())
        
        # Descartar nota mais alta e mais baixa
        notas_ordenadas = sorted(notas)
        notas_validas = notas_ordenadas[1:-1]  # Remove primeira e última
        
        if not notas_validas:
            return None
        
        # Calcular média
        media = statistics.mean(notas_validas)
        
        # Formatar com 2 casas decimais
        return round(media, 2)
    
    def gerar_relatorio(self) -> dict:
        """Gera relatório completo da pontuação"""
        if not self.todas_notas_recebidas():
            return {
                "status": "incompleto",
                "notas_recebidas": len(self.notas_recebidas),
                "notas_esperadas": self.numero_juizes
            }
        
        notas = list(self.notas_recebidas.values())
        nota_final = self.calcular_nota_final()
        
        return {
            "status": "completo",
            "notas_individuais": self.notas_recebidas,
            "nota_descartada_menor": min(notas),
            "nota_descartada_maior": max(notas),
            "notas_utilizadas": sorted(notas)[1:-1],
            "nota_final": nota_final,
            "processado_em": datetime.utcnow().isoformat()
        }


class JoystickManager:
    """Gerenciador central de joysticks e pontuação"""
    
    def __init__(self):
        self.janelas_ativas: Dict[str, CoincidenceWindow] = {}
        self.poomsaes_ativas: Dict[str, PoomsaeScoring] = {}
        self.conexoes_laterais: Dict[str, set] = {}  # {luta_id: {lateral_email1, lateral_email2, ...}}
    
    def criar_janela_coincidencia(self, luta_id: str) -> CoincidenceWindow:
        """Cria uma nova janela de coincidência para uma luta"""
        janela = CoincidenceWindow(luta_id=luta_id)
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
                                 tipo_ponto: str, cor: str) -> Optional[dict]:
        """
        Registra clique de árbitro lateral e verifica validação.
        Retorna ponto validado se houver coincidência.
        """
        # Criar janela se não existir
        if luta_id not in self.janelas_ativas:
            self.criar_janela_coincidencia(luta_id)
        
        janela = self.janelas_ativas[luta_id]
        
        # Se janela expirou, iniciar nova
        if not janela.está_ativa():
            self.criar_janela_coincidencia(luta_id)
            janela = self.janelas_ativas[luta_id]
        
        # Registrar clique
        janela.registrar_clique(lateral_email, tipo_ponto, cor)
        
        # Verificar validação
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
    
    def registrar_nota_poomsae(self, luta_id: str, juiz_email: str, nota: float) -> dict:
        """
        Registra nota de um juiz para Poomsae.
        Retorna status e resultado final se completo.
        """
        if luta_id not in self.poomsaes_ativas:
            raise ValueError(f"Sessão de Poomsae não encontrada para luta {luta_id}")
        
        sessao = self.poomsaes_ativas[luta_id]
        
        if sessao.tempo_expirou():
            raise ValueError("Tempo limite para envio de notas foi ultrapassado")
        
        # Registrar nota
        todas_recebidas = sessao.registrar_nota(juiz_email, nota)
        
        response = {
            "luta_id": luta_id,
            "juiz_email": juiz_email,
            "nota_registrada": nota,
            "notas_recebidas": len(sessao.notas_recebidas),
            "notas_esperadas": sessao.numero_juizes,
            "status": "em_espera"
        }
        
        # Se todas as notas foram recebidas, calcular resultado
        if todas_recebidas:
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
