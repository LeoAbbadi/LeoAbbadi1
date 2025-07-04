# -*- coding: utf-8 -*-

import os
import sqlite3
import requests
from datetime import datetime, timedelta
import json

# --- CONFIGURAÇÕES (DEVEM SER AS MESMAS DO MAIN.PY) ---
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN') # Opcional, dependendo da sua Z-API
DATABASE_FILE = 'bot_database.db'
BOT_NAME = "Cadu"

def send_reminder(phone, user_name):
    """Envia a mensagem de lembrete via Z-API."""
    print(f"Preparando lembrete para {user_name} ({phone})...")
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    message = (
        f"Olá, {user_name}! Sou o {BOT_NAME}, seu assistente de carreira. 👋\n\n"
        "Notei que não conseguimos finalizar seu currículo. Que tal continuarmos de onde paramos? "
        "É só me responder aqui quando estiver pronto. 😉"
    )
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Lembrete enviado com sucesso para {phone}")
            return True
        else:
            print(f"Falha ao enviar lembrete para {phone}: {response.text}")
            return False
    except Exception as e:
        print(f"Erro de conexão ao enviar lembrete para {phone}: {e}")
        return False

def mark_reminder_as_sent(phone):
    """Marca no banco de dados que o lembrete foi enviado para não enviar novamente."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET reminder_sent = 1 WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        print(f"Usuário {phone} marcado como 'lembrete enviado'.")
    except Exception as e:
        print(f"Erro ao atualizar status do lembrete para {phone}: {e}")

def check_for_inactive_users():
    """Verifica o banco de dados por usuários inativos e envia lembretes."""
    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Iniciando verificação de usuários inativos...")
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Usuários que não interagiram nas últimas 24 horas, não completaram o processo E não receberam lembrete
        time_threshold = datetime.now() - timedelta(hours=24)
        
        cursor.execute(
            "SELECT phone, resume_data FROM users WHERE state NOT IN ('completed', 'awaiting_welcome') AND updated_at < ? AND reminder_sent = 0",
            (time_threshold,)
        )
        
        inactive_users = cursor.fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"ERRO: Não foi possível ler o banco de dados: {e}. Certifique-se de que o arquivo main.py já rodou pelo menos uma vez para criar o banco de dados com a estrutura correta.")
        return

    if not inactive_users:
        print("Nenhum usuário inativo para notificar.")
        return

    print(f"Encontrados {len(inactive_users)} usuários inativos para notificar.")
    for user in inactive_users:
        try:
            resume_data = json.loads(user['resume_data'])
            # Pega o primeiro nome para a saudação
            user_name = resume_data.get('nome', 'tudo bem?').split(' ')[0]
            
            if send_reminder(user['phone'], user_name):
                mark_reminder_as_sent(user['phone'])

        except Exception as e:
            print(f"Erro ao processar usuário {user['phone']}: {e}")
    
    print("Verificação finalizada.")

if __name__ == "__main__":
    if not all([ZAPI_INSTANCE_ID, ZAPI_TOKEN]):
        print("ERRO: As variáveis de ambiente da Z-API (ZAPI_INSTANCE_ID, ZAPI_TOKEN) não foram encontradas nos seus 'Secrets'.")
    else:
        check_for_inactive_users()
