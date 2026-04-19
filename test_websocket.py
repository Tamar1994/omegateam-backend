"""
Teste de WebSocket local para validar conexão
"""
import asyncio
import json
import websockets
import time

async def test_websocket_local():
    """Testa WebSocket em localhost"""
    print("=" * 60)
    print("🧪 TESTE DE WEBSOCKET LOCAL")
    print("=" * 60)
    
    # Configurações
    LUTA_ID = "69e2824283fc687d6be324c4"
    EMAIL = "arbitro1@omegateam.com.br"
    EMAIL_ENCODED = "arbitro1%40omegateam.com.br"
    
    # Testar localhost
    url = f"ws://localhost:8000/api/ws/lateral/{LUTA_ID}/{EMAIL_ENCODED}"
    
    print(f"\n🔗 Tentando conectar a: {url}")
    print(f"   Luta ID: {LUTA_ID}")
    print(f"   Email: {EMAIL}")
    
    try:
        async with websockets.connect(url) as websocket:
            print(f"✅ CONECTADO!")
            
            # Enviar teste
            mensagem = {
                "tipo_ponto": "+1",
                "cor": "vermelho",
                "timestamp": time.time()
            }
            
            print(f"\n📤 Enviando: {json.dumps(mensagem)}")
            await websocket.send(json.dumps(mensagem))
            
            # Receber resposta
            resposta = await websocket.recv()
            print(f"📥 Recebido: {resposta}")
            
            # Aguardar um pouco e então desconectar
            await asyncio.sleep(2)
            print("✅ Teste concluído com sucesso!")
            
    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CERTIFIQUE-SE DE QUE O BACKEND ESTÁ RODANDO EM LOCALHOST:8000")
    print("=" * 60 + "\n")
    
    asyncio.run(test_websocket_local())
