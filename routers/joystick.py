"""
Rotas de Joystick com WebSocket para Árbitros Laterais (Tempo Real)
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from database.connection import get_db
from services.joystick_service import joystick_manager
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Joystick"])

# Gerenciador de conexões WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}  # {campeonato_id: {lateral_email: websocket}}
        self.mesario_connections: dict = {}  # {luta_id: websocket}
        self.live_connections: dict = {}  # {campeonato_id: [websocket1, websocket2, ...]} para Live.jsx
    
    async def connect(self, campeonato_id: str, lateral_email: str, websocket: WebSocket):
        """Conecta um árbitro lateral ao WebSocket"""
        try:
            logger.debug(f"  [ACEITANDO] WebSocket...")
            await websocket.accept()
            logger.debug(f"  [ACEITO] WebSocket aceito com sucesso!")
            
            if campeonato_id not in self.active_connections:
                self.active_connections[campeonato_id] = {}
            
            self.active_connections[campeonato_id][lateral_email] = websocket
            logger.debug(f"✅ LATERAL CONECTADO: {lateral_email} → campeonato {campeonato_id}")
            logger.debug(f"   Conexões ativas neste campeonato: {list(self.active_connections[campeonato_id].keys())}")
        except Exception as e:
            logger.debug(f"❌ ERRO AO ACEITAR WEBSOCKET: {type(e).__name__}: {e}")
            raise
    
    async def connect_mesario(self, luta_id: str, numero_quadra: int, websocket: WebSocket):
        """Conecta o Mesário ao WebSocket"""
        await websocket.accept()
        self.mesario_connections[f"{luta_id}:{numero_quadra}"] = websocket
        logger.debug(f"✅ Mesário da quadra {numero_quadra} conectado à luta {luta_id}")
    
    def disconnect(self, campeonato_id: str, lateral_email: str):
        """Desconecta um árbitro lateral"""
        if campeonato_id in self.active_connections:
            if lateral_email in self.active_connections[campeonato_id]:
                del self.active_connections[campeonato_id][lateral_email]
            
            if not self.active_connections[campeonato_id]:
                del self.active_connections[campeonato_id]
        
        logger.debug(f"❌ Lateral {lateral_email} desconectado do campeonato {campeonato_id}")
    
    def disconnect_mesario(self, luta_id: str, numero_quadra: int):
        """Desconecta o Mesário"""
        key = f"{luta_id}:{numero_quadra}"
        if key in self.mesario_connections:
            del self.mesario_connections[key]
        
        logger.debug(f"❌ Mesário da quadra {numero_quadra} desconectado da luta {luta_id}")
    
    async def broadcast_to_luta(self, campeonato_id: str, message: dict):
        """Envia mensagem para todos os árbitros de um campeonato"""
        if campeonato_id not in self.active_connections:
            return
        
        for lateral_email, websocket in list(self.active_connections[campeonato_id].items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"❌ Erro ao enviar para {lateral_email}: {e}")
                self.disconnect(campeonato_id, lateral_email)
    
    async def broadcast_to_all_mesarios(self, message: dict):
        """Envia mensagem para TODOS os Mesários conectados"""
        for key, websocket in list(self.mesario_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"❌ Erro ao enviar para Mesário {key}: {e}")
                luta_id, numero_quadra = key.split(":")
                self.disconnect_mesario(luta_id, int(numero_quadra))
    
    async def notificar_status_laterais(self, campeonato_id: str):
        """Notifica o Mesário que o status dos laterais mudou (alguém conectou/desconectou)"""
        # Pega lista de laterais conectados
        laterais_conectados = list(self.active_connections.get(campeonato_id, {}).keys()) if campeonato_id in self.active_connections else []
        
        mensagem = {
            "status": "laterais_atualizacao",
            "campeonato_id": campeonato_id,
            "laterais_conectados": laterais_conectados,
            "total_laterais": len(laterais_conectados),
            "timestamp": datetime.now().isoformat()
        }
        
        # Enviar para TODOS os Mesários desta luta
        for key, websocket in list(self.mesario_connections.items()):
            # Nota: Mesário armazena como "luta_id:numero_quadra", vamos enviar para todos por enquanto
            try:
                await websocket.send_json(mensagem)
            except Exception as e:
                logger.debug(f"❌ Erro ao notificar Mesário {key}: {e}")

    async def notificar_luta_iniciada(self, campeonato_id: str, luta_data: dict):
        """
        🎬 Notifica TODOS os laterais sobre luta iniciada
        
        Envia:
        {
            "status": "luta_iniciada",
            "luta_id": luta_id,
            "modalidade": "Kyorugui" ou "Poomsae",
            "atleta_vermelho": "Nome",
            "atleta_azul": "Nome",
            "timestamp": ISO
        }
        """
        logger.debug(f"\n{'='*60}")
        logger.debug(f"🎬 NOTIFICANDO LATERAIS - LUTA INICIADA")
        logger.debug(f"{'='*60}")
        logger.debug(f"  Campeonato ID: {campeonato_id}")
        logger.debug(f"  Luta Data: {luta_data}")
        
        # Verificar conexões ativas
        laterais_conectados = list(self.active_connections.get(campeonato_id, {}).keys()) if campeonato_id in self.active_connections else []
        logger.debug(f"  Laterais conectados neste campeonato: {laterais_conectados}")
        logger.debug(f"  Total: {len(laterais_conectados)}")
        
        mensagem = {
            "status": "luta_iniciada",
            "luta_id": luta_data.get("luta_id"),
            "modalidade": luta_data.get("modalidade", "Kyorugui"),
            "atleta_vermelho": luta_data.get("atleta_vermelho", "Atleta 1"),
            "atleta_azul": luta_data.get("atleta_azul", "Atleta 2"),
            "timestamp": datetime.now().isoformat()
        }

        # Enviar para TODOS os laterais deste campeonato
        if campeonato_id in self.active_connections:
            for lateral_email, websocket in list(self.active_connections[campeonato_id].items()):
                try:
                    logger.debug(f"  📤 Enviando luta_iniciada para {lateral_email}...")
                    await websocket.send_json(mensagem)
                    logger.debug(f"  ✅ Enviado com sucesso para {lateral_email}")
                except Exception as e:
                    logger.debug(f"  ❌ Erro ao notificar lateral {lateral_email}: {e}")
        else:
            logger.debug(f"  ⚠️ Nenhuma conexão ativa para campeonato {campeonato_id}")
        
        logger.debug(f"{'='*60}\n")


    async def connect_live(self, campeonato_id: str, websocket: WebSocket):
        """Conecta um cliente Live (TV, display, etc) ao WebSocket"""
        await websocket.accept()
        
        if campeonato_id not in self.live_connections:
            self.live_connections[campeonato_id] = []
        
        self.live_connections[campeonato_id].append(websocket)
        logger.debug(f"✅ LIVE CONECTADO: campeonato {campeonato_id} (Total: {len(self.live_connections[campeonato_id])})")
    
    def disconnect_live(self, campeonato_id: str, websocket: WebSocket):
        """Desconecta um cliente Live"""
        if campeonato_id in self.live_connections:
            if websocket in self.live_connections[campeonato_id]:
                self.live_connections[campeonato_id].remove(websocket)
            
            if not self.live_connections[campeonato_id]:
                del self.live_connections[campeonato_id]
        
        logger.debug(f"❌ LIVE desconectado do campeonato {campeonato_id}")
    
    async def broadcast_luta_update(self, campeonato_id: str, luta_data: dict):
        """
        Envia atualização de status de luta para TODOS os clientes Live
        
        Envia:
        {
            "tipo": "luta_atualizada",
            "luta_id": luta_id,
            "status": "Em Andamento" | "Aguardando Chamada" | "Encerrada",
            "placar": {...},
            "timestamp": ISO
        }
        """
        mensagem = {
            "tipo": "luta_atualizada",
            "luta_id": luta_data.get("_id"),
            "status": luta_data.get("status"),
            "placar": {
                "red_pontos": luta_data.get("pontos_vermelho", 0),
                "blue_pontos": luta_data.get("pontos_azul", 0),
                "red_faltas": luta_data.get("faltas_vermelho", 0),
                "blue_faltas": luta_data.get("faltas_azul", 0),
                "round": luta_data.get("round", 1),
                "turno_poomsae": luta_data.get("turno_poomsae")
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if campeonato_id in self.live_connections:
            for websocket in list(self.live_connections[campeonato_id]):
                try:
                    await websocket.send_json(mensagem)
                except Exception as e:
                    logger.debug(f"❌ Erro ao enviar para Live {campeonato_id}: {e}")
                    self.disconnect_live(campeonato_id, websocket)


# Instância global de gerenciador de conexões
manager = ConnectionManager()


@router.websocket("/ws/lateral/{campeonato_id}/{lateral_email}")
async def websocket_lateral(websocket: WebSocket, campeonato_id: str, lateral_email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    WebSocket para árbitro lateral enviar pontos e receber confirmações.
    
    Fluxo:
    1. Lateral conecta ao WebSocket (identificado por campeonato_id, não luta_id)
    2. Lateral carrega em botão ("+1", "+2", "+3")
    3. Servidor registra clique e aguarda coincidência
    4. Se houver coincidência (2+ árbitros), ponto é validado
    5. Confirmação é enviada de volta para todos os laterais
    """
    logger.debug(f"\n{'='*60}")
    logger.debug(f"🔌 WEBSOCKET LATERAL - TENTATIVA DE CONEXÃO")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Hora: {datetime.now().isoformat()}")
    logger.debug(f"  Campeonato ID: {campeonato_id}")
    logger.debug(f"  Email: {lateral_email}")
    logger.debug(f"  Headers: {dict(websocket.headers)}")
    logger.debug(f"{'='*60}\n")
    
    try:
        await manager.connect(campeonato_id, lateral_email, websocket)
        logger.debug(f"✅ CONEXÃO ACEITA: lateral={lateral_email}, campeonato={campeonato_id}")
        
        # 🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL CONECTOU
        await manager.notificar_status_laterais(campeonato_id)
    except Exception as e:
        logger.debug(f"❌ ERRO AO CONECTAR: {e}")
        raise
    
    try:
        while True:
            # Receber mensagem do lateral
            data = await websocket.receive_json()
            
            # ✅ IMPORTANTE: Extrair luta_id da mensagem (enviado pelo frontend)
            luta_id = data.get("luta_id")
            if not luta_id and data.get("tipo") != "lateral_pronto":
                # Para pontos, luta_id é obrigatório
                await websocket.send_json({
                    "status": "erro",
                    "mensagem": "luta_id não encontrado na mensagem"
                })
                continue
            
            # ✋ HANDLER: Lateral marca como pronto
            if data.get("tipo") == "lateral_pronto":
                logger.debug(f"\n{'='*60}")
                logger.debug(f"✋ LATERAL MARCANDO COMO PRONTO")
                logger.debug(f"{'='*60}")
                logger.debug(f"  Email: {lateral_email}")
                logger.debug(f"  Campeonato: {campeonato_id}")
                logger.debug(f"  Timestamp: {data.get('timestamp')}")
                
                # 🔍 Procurar qual quadra tem este lateral
                quadra = await db.quadras.find_one({
                    "campeonato_id": campeonato_id,
                    "$or": [
                        {"lateral1_email": lateral_email},
                        {"lateral2_email": lateral_email},
                        {"lateral3_email": lateral_email},
                        {"lateral4_email": lateral_email},
                        {"lateral5_email": lateral_email}
                    ]
                })
                
                if quadra:
                    # 🎯 Encontrar qual slot (1-5) este lateral ocupa
                    numero_quadra = quadra.get("numero_quadra")
                    lateral_slot = None
                    for i in range(1, 6):
                        if quadra.get(f"lateral{i}_email") == lateral_email:
                            lateral_slot = i
                            break
                    
                    if lateral_slot:
                        # ✅ Atualizar no banco: lateral{N}_ready = true
                        await db.quadras.update_one(
                            {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                            {"$set": {f"lateral{lateral_slot}_ready": True}}
                        )
                        logger.debug(f"  ✅ Marcado como pronto: lateral{lateral_slot} na quadra {numero_quadra}")
                        logger.debug(f"{'='*60}\n")
                        
                        # 📡 Notificar Mesário que status mudou
                        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
                        
                        # ✅ Confirmar para o lateral
                        await websocket.send_json({
                            "status": "pronto_confirmado",
                            "mensagem": "Você está pronto para a luta!",
                            "timestamp": data.get("timestamp")
                        })
                    else:
                        logger.debug(f"  ❌ Não encontrou qual slot o lateral ocupa")
                        logger.debug(f"{'='*60}\n")
                else:
                    logger.debug(f"  ❌ Nenhuma quadra encontrada com este lateral")
                    logger.debug(f"{'='*60}\n")
                
                continue
            
            # Validar dados para pontos
            if "tipo_ponto" not in data or "cor" not in data:
                await websocket.send_json({
                    "status": "erro",
                    "mensagem": "Faltam campos: tipo_ponto e cor"
                })
                continue
            
            tipo_ponto = data["tipo_ponto"]  # "+1", "+2", "+3"
            cor = data["cor"]  # "vermelho" ou "azul"
            
            # 📊 Contar quantos laterais conectados para validação por maioria
            total_laterais_conectados = len(manager.active_connections.get(campeonato_id, {}))
            
            # Registrar clique e verificar validação (MAIORIA ABSOLUTA)
            ponto_validado = joystick_manager.registrar_clique_lateral(
                luta_id=luta_id,
                lateral_email=lateral_email,
                tipo_ponto=tipo_ponto,
                cor=cor,
                total_laterais=total_laterais_conectados  # ✅ Passa o total de laterais
            )
            
            # Enviar confirmação de recebimento ao lateral
            await websocket.send_json({
                "status": "clique_recebido",
                "tipo_ponto": tipo_ponto,
                "cor": cor,
                "timestamp": data.get("timestamp")
            })
            
            # Se ponto foi validado, enviar para todos
            if ponto_validado:
                mensagem_validacao = {
                    "status": "ponto_validado",
                    "luta_id": luta_id,
                    "cor": ponto_validado["cor"],
                    "pontos": ponto_validado["pontos"],
                    "arbitros_confirmados": ponto_validado["arbitros_confirmados"],
                    "validado_em": ponto_validado["validado_em"]
                }
                
                # Broadcast para todos os laterais deste campeonato
                await manager.broadcast_to_luta(campeonato_id, mensagem_validacao)
                
                # Broadcast para todos os Mesários
                await manager.broadcast_to_all_mesarios(mensagem_validacao)
    
    except WebSocketDisconnect:
        logger.debug(f"\n{'='*60}")
        logger.debug(f"❌ WEBSOCKET LATERAL DESCONECTADO")
        logger.debug(f"{'='*60}")
        logger.debug(f"  Hora: {datetime.now().isoformat()}")
        logger.debug(f"  Lateral: {lateral_email}")
        logger.debug(f"  Campeonato: {campeonato_id}")
        logger.debug(f"{'='*60}\n")
        manager.disconnect(campeonato_id, lateral_email)
        
        # � RESETAR O READY DO LATERAL QUE DESCONECTOU
        quadra = await db.quadras.find_one({
            "campeonato_id": campeonato_id,
            "$or": [
                {"lateral1_email": lateral_email},
                {"lateral2_email": lateral_email},
                {"lateral3_email": lateral_email},
                {"lateral4_email": lateral_email},
                {"lateral5_email": lateral_email}
            ]
        })
        
        if quadra:
            numero_quadra = quadra.get("numero_quadra")
            for i in range(1, 6):
                if quadra.get(f"lateral{i}_email") == lateral_email:
                    # ❌ Resetar ready para false
                    await db.quadras.update_one(
                        {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                        {"$set": {f"lateral{i}_ready": False}}
                    )
                    logger.debug(f"  🔴 Resetado: lateral{i}_ready = False (lateral desconectou)")
                    break
        
        # �🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL DESCONECTOU
        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
    except Exception as e:
        logger.debug(f"\n{'='*60}")
        logger.debug(f"❌ ERRO INESPERADO NO WEBSOCKET LATERAL")
        logger.debug(f"{'='*60}")
        logger.debug(f"  Tipo de erro: {type(e).__name__}")
        logger.debug(f"  Mensagem: {e}")
        logger.debug(f"  Lateral: {lateral_email}")
        logger.debug(f"  Campeonato: {campeonato_id}")
        logger.debug(f"{'='*60}\n")
        manager.disconnect(campeonato_id, lateral_email)
        
        # � RESETAR O READY DO LATERAL (POR ERRO)
        quadra = await db.quadras.find_one({
            "campeonato_id": campeonato_id,
            "$or": [
                {"lateral1_email": lateral_email},
                {"lateral2_email": lateral_email},
                {"lateral3_email": lateral_email},
                {"lateral4_email": lateral_email},
                {"lateral5_email": lateral_email}
            ]
        })
        
        if quadra:
            numero_quadra = quadra.get("numero_quadra")
            for i in range(1, 6):
                if quadra.get(f"lateral{i}_email") == lateral_email:
                    # ❌ Resetar ready para false
                    await db.quadras.update_one(
                        {"campeonato_id": campeonato_id, "numero_quadra": numero_quadra},
                        {"$set": {f"lateral{i}_ready": False}}
                    )
                    logger.debug(f"  🔴 Resetado: lateral{i}_ready = False (erro na conexão)")
                    break
        
        # �🔔 NOTIFICAR O MESÁRIO QUE UM LATERAL FOI DESCONECTADO (POR ERRO)
        asyncio.create_task(manager.notificar_status_laterais(campeonato_id))
        raise


@router.websocket("/ws/poomsae/{luta_id}/{juiz_email}")
async def websocket_poomsae(websocket: WebSocket, luta_id: str, juiz_email: str):
    """
    WebSocket para juiz lateral enviar notas de Poomsae - NOVO SISTEMA.
    
    NOVO FLUXO:
    1. Frontend envia: tipo='poomsae_accuracy', atletaAtual, nota_accuracy
    2. Backend registra e confirma
    3. Frontend envia: tipo='poomsae_apresentacao', atletaAtual, velocidade, ritmo, expressao
    4. Backend registra e se completo, envia resultado final
    """
    await websocket.accept()
    
    try:
        # Receber ACCURACY (primeira mensagem)
        data_accuracy = await websocket.receive_json()
        
        if data_accuracy.get("tipo") != "poomsae_accuracy":
            await websocket.send_json({
                "status": "erro",
                "mensagem": "Esperava tipo='poomsae_accuracy' como primeira mensagem"
            })
            await websocket.close()
            return
        
        nota_accuracy = float(data_accuracy.get("nota_accuracy", 0))
        atleta_atual = data_accuracy.get("atletaAtual", "vermelho")
        
        # Criar sessão se não existir
        if luta_id not in joystick_manager.poomsaes_ativas:
            # Deduzir número de juízes (assumir 2 para Poomsae)
            joystick_manager.criar_sessao_poomsae(luta_id, numero_juizes=2)
        
        # Registrar ACCURACY
        resultado_acc = joystick_manager.registrar_accuracy_poomsae(
            luta_id=luta_id,
            juiz_email=juiz_email,
            nota=nota_accuracy,
            atleta=atleta_atual
        )
        
        # Confirmar recebimento de ACCURACY
        await websocket.send_json({
            "tipo": "accuracy_confirmada",
            "status": "ok",
            "atleta": atleta_atual,
            "nota_accuracy": nota_accuracy,
            "votos_accuracy": resultado_acc["votos_para_atleta"],
            "votos_esperados": resultado_acc["votos_esperados"],
            "mensagem": "Accuracy registrada. Aguardando apresentação..."
        })
        
        # Receber APRESENTAÇÃO (segunda mensagem)
        data_apresentacao = await websocket.receive_json()
        
        if data_apresentacao.get("tipo") != "poomsae_apresentacao":
            await websocket.send_json({
                "status": "erro",
                "mensagem": "Esperava tipo='poomsae_apresentacao' como segunda mensagem"
            })
            await websocket.close()
            return
        
        velocidade = float(data_apresentacao.get("nota_velocidade", 0))
        ritmo = float(data_apresentacao.get("nota_ritmo", 0))
        expressao = float(data_apresentacao.get("nota_expressao", 0))
        atleta = data_apresentacao.get("atletaAtual", atleta_atual)
        
        # Registrar APRESENTAÇÃO
        resultado_apre = joystick_manager.registrar_apresentacao_poomsae(
            luta_id=luta_id,
            juiz_email=juiz_email,
            velocidade=velocidade,
            ritmo=ritmo,
            expressao=expressao,
            atleta=atleta
        )
        
        # Confirmar recebimento de APRESENTAÇÃO
        await websocket.send_json({
            "tipo": "apresentacao_confirmada",
            "status": "ok",
            "atleta": atleta,
            "velocidade": velocidade,
            "ritmo": ritmo,
            "expressao": expressao,
            "votos_apresentacao": resultado_apre["votos_para_atleta"],
            "votos_esperados": resultado_apre["votos_esperados"]
        })
        
        # Se resultado está completo, enviar resultado final
        if resultado_apre["status"] == "completo":
            relatorio = resultado_apre.get("relatorio", {})
            
            resultado_final_msg = {
                "tipo": "poomsae_resultado_final",
                "status": "resultado_final",
                "resultado_final": {
                    "notas": {
                        "vermelho": relatorio.get("nota_final_vermelho", 0),
                        "azul": relatorio.get("nota_final_azul", 0)
                    },
                    "detalhes": relatorio.get("notas", {}),
                    "vencedor": relatorio.get("vencedor")
                },
                "mensagem": f"Poomsae completo! Vencedor: {relatorio.get('vencedor')}"
            }
            
            # Enviar para este juiz (confirmação)
            await websocket.send_json(resultado_final_msg)
            
            # 📢 BROADCAST para TODOS os Mesários conectados
            await broadcast_poomsae_resultado(luta_id, resultado_final_msg)
        else:
            # Aguardando outros juízes
            await websocket.send_json({
                "tipo": "poomsae_computando",
                "status": "computando",
                "atleta": atleta,
                "mensagem": f"Computando notas... Aguardando outros árbitros."
            })
    
    except ValueError as e:
        await websocket.send_json({
            "status": "erro",
            "mensagem": f"Erro ao processar notas: {str(e)}"
        })
        await websocket.close()
    except WebSocketDisconnect:
        logger.debug(f"Juiz {juiz_email} desconectado da sessão Poomsae {luta_id}")


@router.post("/lutas/{luta_id}/notificar-fim-luta")
async def notificar_fim_luta(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Notifica TODOS os laterais que a luta foi FINALIZADA.
    Chamado pelo Mesário ao encerrar a luta.
    
    Envia:
    {
        "status": "luta_finalizada",
        "luta_id": luta_id,
        "timestamp": ISO
    }
    """
    logger.debug(f"\n{'='*60}")
    logger.debug(f"🎬 NOTIFICANDO LATERAIS - LUTA FINALIZADA")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Luta ID: {luta_id}")
    
    # Procurar a luta para pegar campeonato_id
    try:
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
    except:
        luta = await db.lutas.find_one({"_id": luta_id})
    
    if not luta:
        logger.debug(f"  ❌ Luta não encontrada")
        logger.debug(f"{'='*60}\n")
        return {"status": "erro", "mensagem": "Luta não encontrada"}
    
    campeonato_id = luta.get("campeonato_id")
    
    mensagem = {
        "status": "luta_finalizada",
        "luta_id": luta_id,
        "timestamp": datetime.now().isoformat()
    }
    
    # Enviar para TODOS os laterais deste campeonato
    laterais_notificados = 0
    if campeonato_id in manager.active_connections:
        for lateral_email, websocket in list(manager.active_connections[campeonato_id].items()):
            try:
                await websocket.send_json(mensagem)
                logger.debug(f"  📤 Enviando para {lateral_email}... ✅")
                laterais_notificados += 1
            except Exception as e:
                logger.debug(f"  ❌ Erro ao notificar lateral {lateral_email}: {e}")
    
    logger.debug(f"  ✅ Notificação enviada para {laterais_notificados} laterais")
    logger.debug(f"{'='*60}\n")
    
    return {
        "status": "ok",
        "mensagem": "Luta finalizada notificada",
        "laterais_notificados": laterais_notificados
    }


@router.get("/poomsae/{luta_id}/validar-mesario-gate")
async def validar_mesario_gate(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    ✅ MESÁRIO GATE - Verifica se TODOS os juízes registraram as notas
    
    Retorna:
    - todos_registraram: bool (True = pode passar para próximo)
    - status_juizes: dict com status de cada juiz
    - mensagem: string descritiva
    
    BLOQUEIA o mesário se nem todos registraram!
    """
    try:
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
    except:
        luta = await db.lutas.find_one({"_id": luta_id})
    
    if not luta:
        return {
            "todos_registraram": False,
            "status": "erro",
            "mensagem": "Luta não encontrada"
        }
    
    # Verificar se a sessão de Poomsae existe
    if luta_id not in joystick_manager.poomsaes_ativas:
        return {
            "todos_registraram": False,
            "status": "aguardando",
            "mensagem": "Nenhum juiz registrou notas ainda"
        }
    
    sessao = joystick_manager.poomsaes_ativas[luta_id]
    
    # Verificar accuracy e apresentação
    accuracy_registrados = sessao.get("accuracy_por_atleta", {})
    apresentacao_registrados = sessao.get("apresentacao_por_atleta", {})
    
    # Precisa de votos para VERMELHO e AZUL em AMBAS as fases
    vermelho_accuracy = len(accuracy_registrados.get("vermelho", []))
    azul_accuracy = len(accuracy_registrados.get("azul", []))
    vermelho_apresentacao = len(apresentacao_registrados.get("vermelho", []))
    azul_apresentacao = len(apresentacao_registrados.get("azul", []))
    
    # Número esperado de juízes (padrão 2, mas checar na luta)
    num_juizes = sessao.get("numero_juizes", 2)
    
    # Status de cada atleta
    status_juizes = {
        "vermelho": {
            "accuracy": {"registrados": vermelho_accuracy, "esperados": num_juizes},
            "apresentacao": {"registrados": vermelho_apresentacao, "esperados": num_juizes}
        },
        "azul": {
            "accuracy": {"registrados": azul_accuracy, "esperados": num_juizes},
            "apresentacao": {"registrados": azul_apresentacao, "esperados": num_juizes}
        }
    }
    
    # Verificar se TODOS registraram
    todos_registraram = (
        vermelho_accuracy >= num_juizes and
        azul_accuracy >= num_juizes and
        vermelho_apresentacao >= num_juizes and
        azul_apresentacao >= num_juizes
    )
    
    if todos_registraram:
        return {
            "todos_registraram": True,
            "status": "ok",
            "mensagem": f"✅ Todos os {num_juizes} juízes registraram as notas!",
            "status_juizes": status_juizes
        }
    else:
        faltando = []
        if vermelho_accuracy < num_juizes:
            faltando.append(f"Accuracy Vermelho ({vermelho_accuracy}/{num_juizes})")
        if azul_accuracy < num_juizes:
            faltando.append(f"Accuracy Azul ({azul_accuracy}/{num_juizes})")
        if vermelho_apresentacao < num_juizes:
            faltando.append(f"Apresentação Vermelho ({vermelho_apresentacao}/{num_juizes})")
        if azul_apresentacao < num_juizes:
            faltando.append(f"Apresentação Azul ({azul_apresentacao}/{num_juizes})")
        
        return {
            "todos_registraram": False,
            "status": "aguardando",
            "mensagem": f"⏳ Aguardando notas: {', '.join(faltando)}",
            "status_juizes": status_juizes,
            "bloqueado": True
        }


@router.websocket("/ws/mesario/{luta_id}/{numero_quadra}")
async def websocket_mesario(websocket: WebSocket, luta_id: str, numero_quadra: int):
    """
    WebSocket para Mesário receber pontos validados em tempo real.
    
    Fluxo:
    1. Mesário conecta ao WebSocket
    2. Aguarda mensagens de pontos validados dos laterais
    3. Quando um ponto é validado pela Coincidence Window, recebe notificação
    4. Atualiza automaticamente o placar
    """
    logger.debug(f"\n{'='*60}")
    logger.debug(f"🔌 WEBSOCKET MESARIO - TENTATIVA DE CONEXÃO")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Hora: {datetime.now().isoformat()}")
    logger.debug(f"  Luta ID: {luta_id}")
    logger.debug(f"  Número Quadra: {numero_quadra}")
    logger.debug(f"  Headers: {dict(websocket.headers)}")
    logger.debug(f"{'='*60}\n")
    
    try:
        await manager.connect_mesario(luta_id, numero_quadra, websocket)
    except Exception as e:
        logger.debug(f"❌ ERRO AO CONECTAR MESARIO: {e}")
        raise
    
    try:
        while True:
            # Manter conexão aberta e aguardar mensagens
            data = await websocket.receive_json()
            
            # Se receber "ping", responder com "pong"
            if data.get("tipo") == "ping":
                await websocket.send_json({"tipo": "pong"})
    
    except WebSocketDisconnect:
        logger.debug(f"\n{'='*60}")
        logger.debug(f"❌ WEBSOCKET MESARIO DESCONECTADO")
        logger.debug(f"{'='*60}")
        logger.debug(f"  Hora: {datetime.now().isoformat()}")
        logger.debug(f"  Luta: {luta_id}")
        logger.debug(f"  Quadra: {numero_quadra}")
        logger.debug(f"{'='*60}\n")
        manager.disconnect_mesario(luta_id, numero_quadra)
        manager.disconnect_mesario(luta_id, numero_quadra)


# ========================================
# WEBSOCKET PARA MESÁRIO - POOMSAE
# ========================================
# Novo storage para Mesários conectados ao Poomsae
poomsae_mesario_connections: dict = {}  # {luta_id: [websocket1, websocket2, ...]}

@router.websocket("/ws/mesario/{luta_id}")
async def websocket_mesario_poomsae(websocket: WebSocket, luta_id: str):
    """
    WebSocket para Mesário receber resultados de Poomsae em tempo real.
    
    Fluxo:
    1. Mesário conecta ao WebSocket
    2. Aguarda resultados do Poomsae quando todos os juízes submetem
    3. Quando resultado está completo, recebe: poomsae_resultado_final
    4. Atualiza automaticamente o placar
    """
    logger.debug(f"\n{'='*60}")
    logger.debug(f"🔌 WEBSOCKET MESÁRIO POOMSAE - TENTATIVA DE CONEXÃO")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Hora: {datetime.now().isoformat()}")
    logger.debug(f"  Luta ID: {luta_id}")
    logger.debug(f"  Headers: {dict(websocket.headers)}")
    logger.debug(f"{'='*60}\n")
    
    try:
        await websocket.accept()
        
        # Adicionar à lista de Mesários conectados para este Poomsae
        if luta_id not in poomsae_mesario_connections:
            poomsae_mesario_connections[luta_id] = []
        
        poomsae_mesario_connections[luta_id].append(websocket)
        logger.debug(f"✅ MESÁRIO POOMSAE CONECTADO à luta {luta_id}")
        logger.debug(f"   Mesários conectados: {len(poomsae_mesario_connections[luta_id])}")
        
        # Enviar confirmação de conexão
        await websocket.send_json({
            "tipo": "mesario_poomsae_conectado",
            "luta_id": luta_id,
            "mensagem": "Conectado! Aguardando resultados do Poomsae..."
        })
        
        # Manter conexão aberta
        while True:
            data = await websocket.receive_json()
            
            # Se receber "ping", responder com "pong"
            if data.get("tipo") == "ping":
                await websocket.send_json({"tipo": "pong"})
    
    except WebSocketDisconnect:
        logger.debug(f"\n{'='*60}")
        logger.debug(f"❌ WEBSOCKET MESÁRIO POOMSAE DESCONECTADO")
        logger.debug(f"{'='*60}")
        logger.debug(f"  Hora: {datetime.now().isoformat()}")
        logger.debug(f"  Luta: {luta_id}")
        logger.debug(f"{'='*60}\n")
        
        if luta_id in poomsae_mesario_connections:
            try:
                poomsae_mesario_connections[luta_id].remove(websocket)
            except ValueError:
                pass
            
            if not poomsae_mesario_connections[luta_id]:
                del poomsae_mesario_connections[luta_id]


async def broadcast_poomsae_resultado(luta_id: str, resultado_data: dict):
    """
    Envia resultado final do Poomsae para TODOS os Mesários conectados
    """
    logger.debug(f"\n{'='*60}")
    logger.debug(f"📢 BROADCAST POOMSAE RESULTADO")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Luta: {luta_id}")
    logger.debug(f"  Resultado: {resultado_data.get('resultado_final', {}).get('vencedor')}")
    logger.debug(f"{'='*60}\n")
    
    if luta_id not in poomsae_mesario_connections:
        logger.debug(f"⚠️ Nenhum Mesário conectado para {luta_id}")
        return
    
    mensagem = {
        "tipo": "poomsae_resultado_final",
        "status": "resultado_final",
        "resultado_final": resultado_data.get("resultado_final", {}),
        "mensagem": resultado_data.get("mensagem", "Resultado do Poomsae")
    }
    
    desconectados = []
    for websocket in poomsae_mesario_connections[luta_id]:
        try:
            await websocket.send_json(mensagem)
            logger.debug(f"✅ Enviado para Mesário")
        except Exception as e:
            logger.debug(f"❌ Erro ao enviar para Mesário: {e}")
            desconectados.append(websocket)
    
    # Limpar desconectados
    for ws in desconectados:
        try:
            poomsae_mesario_connections[luta_id].remove(ws)
        except ValueError:
            pass


# ===== ENDPOINTS HTTP (complementares) =====

@router.post("/lutas/{luta_id}/joystick/iniciar-kyorugui")
async def iniciar_kyorugui(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Inicia uma nova janela de coincidência para Kyorugui"""
    joystick_manager.criar_janela_coincidencia(luta_id)
    
    return {
        "status": "iniciado",
        "luta_id": luta_id,
        "tipo": "kyorugui",
        "janela_duracao_ms": 1500
    }


@router.post("/lutas/{luta_id}/joystick/iniciar-poomsae")
async def iniciar_poomsae(
    luta_id: str, 
    numero_juizes: int = 3,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Inicia uma nova sessão de Poomsae"""
    sessao = joystick_manager.criar_sessao_poomsae(luta_id, numero_juizes)
    
    return {
        "status": "iniciado",
        "luta_id": luta_id,
        "tipo": "poomsae",
        "numero_juizes": numero_juizes,
        "timeout_segundos": sessao.timeout_segundos
    }


@router.get("/lutas/{luta_id}/joystick/status-poomsae")
async def status_poomsae(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Obtém status atual da sessão de Poomsae"""
    status = joystick_manager.obter_status_poomsae(luta_id)
    return status


@router.get("/lutas/{luta_id}/joystick/conexoes-ativas")
async def conexoes_ativas(luta_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lista árbitros laterais conectados a uma luta"""
    if luta_id not in manager.active_connections:
        return {"luta_id": luta_id, "laterais_conectado": []}
    
    laterais = list(manager.active_connections[luta_id].keys())
    
    return {
        "luta_id": luta_id,
        "laterais_conectados": laterais,
        "total": len(laterais)
    }


# ===== WEBSOCKET PARA LIVE (TV/DISPLAYS) =====

@router.websocket("/ws/live/{campeonato_id}")
async def websocket_live(websocket: WebSocket, campeonato_id: str):
    """
    WebSocket para Live.jsx - recebe atualizações em tempo real de mudanças de status de lutas
    
    Fluxo:
    1. Cliente Live (TV, display) conecta ao WebSocket
    2. Backend envia atualizações quando status de luta muda
    3. Live.jsx atualiza a tela em tempo real sem polling
    """
    try:
        await manager.connect_live(campeonato_id, websocket)
        
        while True:
            # Aguarda mensagens do cliente (pode ser heartbeat ou refresh request)
            try:
                data = await websocket.receive_json()
                
                if data.get("tipo") == "refresh_request":
                    # Cliente solicitou refresh completo - aqui ele deveria fazer HTTP GET
                    logger.debug(f"📺 Live {campeonato_id} solicitou refresh")
                    
            except Exception as e:
                # Se receber texto em vez de JSON (heartbeat), apenas ignora
                pass
                
    except Exception as e:
        logger.debug(f"❌ Erro no WebSocket Live: {e}")
    finally:
        manager.disconnect_live(campeonato_id, websocket)


@router.get("/joystick/health")
async def joystick_health():
    """Health check para o sistema de WebSocket do Joystick"""
    import fastapi
    import starlette
    
    return {
        "status": "ok",
        "mensagem": "Sistema de Joystick está pronto para WebSocket",
        "diagnostico": {
            "fastapi_version": fastapi.__version__,
            "starlette_version": starlette.__version__,
            "websocket_suportado": True,
            "tempo_servidor": datetime.now().isoformat()
        },
        "websocket_endpoints": [
            "/api/ws/lateral/{luta_id}/{lateral_email}",
            "/api/ws/mesario/{luta_id}/{numero_quadra}",
            "/api/ws/poomsae/{luta_id}/{juiz_email}",
            "/api/ws/live/{campeonato_id}"
        ],
        "conexoes_ativas": {
            "laterais": sum(len(emails) for emails in manager.active_connections.values()),
            "mesarios": len(manager.mesario_connections),
            "lutas_ativas": len(manager.active_connections),
            "detalhe_laterais": {
                luta_id: list(emails.keys()) 
                for luta_id, emails in manager.active_connections.items()
            }
        },
        "dicas_para_debug": [
            "Se receber erro 1006: verifique se o servidor está rodando",
            "WebSocket requer upgrade HTTP 101, verificar proxy/firewall",
            "URL deve usar wss:// em produção (Render com https)"
        ]
    }


@router.post("/lutas/{luta_id}/notificar-laterais")
async def notificar_laterais_luta_iniciada(luta_id: str, dados: dict, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    🎬 Notifica todos os laterais que a luta iniciou
    
    Chamado pelo Mesário quando puxa a próxima luta.
    Envia modalidade (Kyorugui/Poomsae) e dados do atletas para lateral renderizar joystick correto.
    """
    from bson import ObjectId
    
    logger.debug(f"\n{'='*60}")
    logger.debug(f"🎬 NOTIFICANDO LATERAIS SOBRE LUTA INICIADA")
    logger.debug(f"{'='*60}")
    logger.debug(f"  Luta ID: {luta_id}")
    logger.debug(f"  Dados: {dados}")
    
    try:
        # ⚠️ IMPORTANTE: Buscar a luta no banco para descobrir seu campeonato_id
        # Os laterals conectam via campeonato_id, não via luta_id!
        luta = await db.lutas.find_one({"_id": ObjectId(luta_id)})
        
        if not luta:
            raise HTTPException(status_code=404, detail="Luta não encontrada")
        
        campeonato_id = luta.get("campeonato_id")
        logger.debug(f"  Campeonato ID: {campeonato_id}")
        
        # Prepara dados da luta para enviar
        luta_data = {
            "luta_id": luta_id,  # ✅ Enviar luta_id também para frontend
            "modalidade": dados.get("modalidade", "Kyorugui"),
            "atleta_vermelho": dados.get("atleta_vermelho", "Atleta 1"),
            "atleta_azul": dados.get("atleta_azul", "Atleta 2")
        }
        
        # ✅ Notifica laterals usando campeonato_id (assim encontra as conexões)
        await manager.notificar_luta_iniciada(campeonato_id, luta_data)
        
        logger.debug(f"✅ Notificação enviada para laterais")
        logger.debug(f"{'='*60}\n")
        
        return {
            "status": "sucesso",
            "mensagem": "Laterais notificados sobre luta iniciada",
            "luta_id": luta_id,
            "campeonato_id": campeonato_id,
            "luta_data": luta_data
        }
    except Exception as e:
        logger.debug(f"❌ ERRO ao notificar laterais: {e}")
        logger.debug(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Erro ao notificar laterais: {str(e)}")


@router.get("/campeonatos/{camp_id}/minha-posicao-juiz/{email}")
async def minha_posicao_juiz(camp_id: str, email: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Retorna o número do juiz (1-7) de um árbitro lateral com base na configuração da quadra."""
    for i in range(1, 8):
        campo = f"lateral{i}_email"
        quadra = await db.quadras.find_one({"campeonato_id": camp_id, campo: email})
        if quadra:
            return {"numero_juiz": i, "quadra_numero": quadra.get("numero_quadra", i)}
    raise HTTPException(status_code=404, detail="Email não encontrado como juiz neste campeonato")
