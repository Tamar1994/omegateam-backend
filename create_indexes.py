"""
Script para criar índices MongoDB para o sistema de Poomsae WT
Execute uma vez: python create_indexes.py
"""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def create_indexes():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client.omegateam
    
    print("Criando índices MongoDB para Poomsae WT...")
    
    # Atletas
    await db.poomsae_atletas.create_index("email", unique=True)
    await db.poomsae_atletas.create_index("nacionalidade")
    await db.poomsae_atletas.create_index("divisao_etaria")
    print("  ✓ poomsae_atletas")
    
    # Campeonatos
    await db.poomsae_campeonatos.create_index("status")
    await db.poomsae_campeonatos.create_index("timestamp_criacao")
    print("  ✓ poomsae_campeonatos")
    
    # Inscrições
    await db.poomsae_inscricoes.create_index("campeonato_id")
    await db.poomsae_inscricoes.create_index([("campeonato_id", 1), ("categoria", 1)])
    await db.poomsae_inscricoes.create_index("atletas_ids")
    await db.poomsae_inscricoes.create_index("status")
    print("  ✓ poomsae_inscricoes")
    
    # Juízes
    await db.poomsae_juizes.create_index("email", unique=True)
    await db.poomsae_juizes.create_index("classe")
    await db.poomsae_juizes.create_index("tipo_funcao")
    print("  ✓ poomsae_juizes")

    # Matches (Fase 2)
    await db.poomsae_matches.create_index("campeonato_id")
    await db.poomsae_matches.create_index([("campeonato_id", 1), ("divisao", 1), ("rodada", 1)])
    await db.poomsae_matches.create_index("status")
    await db.poomsae_matches.create_index("inscricao_id")
    print("  ✓ poomsae_matches")

    # Scores (Fase 2)
    await db.poomsae_scores.create_index([("match_id", 1), ("juiz_id", 1)], unique=True)
    await db.poomsae_scores.create_index("match_id")
    print("  ✓ poomsae_scores")
    
    print("\nÍndices criados com sucesso!")
    client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
