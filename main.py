# -*- coding: utf-8 -*-

# ==============================================================================
# --- IMPORTAÇÕES COMPLETAS
# ==============================================================================
import os
import sqlite3
import json
import re
from datetime import datetime
import requests
import base64
from flask import Flask, request, jsonify
from fpdf import FPDF
from pypix import Pix

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"
DATABASE_FILE = "bot_database.db"

def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            state TEXT,
            resume_data TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("--> Banco de dados inicializado com sucesso.")

init_database()

# --- CONFIGURAÇÕES DE API (LIDAS DO AMBIENTE) ---
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')
PIX_RECIPIENT_NAME = os.environ.get('PIX_RECIPIENT_NAME', "Seu Nome Completo")
PIX_CITY = os.environ.get('PIX_CITY', "Sua Cidade")
PIX_KEY = os.environ.get('PIX_KEY')
PLANO_BASICO_PRECO = 5.99

# ==============================================================================
# --- FUNÇÕES CORE DO BOT
# ==============================================================================

def get_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (phone, state, resume_data) VALUES (?, ?, ?)",
        (phone, 'awaiting_welcome', json.dumps({}))
    )
    conn.commit()
    conn.close()
    return get_user(phone)

def update_user_state(phone, state):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ? WHERE phone = ?", (state, phone))
    conn.commit()
    conn.close()

def update_resume_data(phone, new_data_dict):
    user = get_user(phone)
    if not user: return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data_dict)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET resume_data = ? WHERE phone = ?", (json.dumps(resume_data), phone))
    conn.commit()
    conn.close()

def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Z-API Erro ao enviar mensagem: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Erro de conexão ao enviar mensagem Z-API: {e}")
        return None

def send_whatsapp_document(phone, doc_path, filename):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response
    except Exception as e:
        print(f"Erro ao enviar documento Z-API: {e}")
        return None

def generate_resume_pdf(resume_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, 'Currículo Profissional', 0, 1, 'C')
    pdf.ln(10)
    
    # Adiciona os dados coletados de forma organizada
    for key, value in resume_data.items():
        if key not in ['phone', 'state']: # Ignora campos de controle
            pdf.set_font("Arial", 'B', 12)
            # Formata a chave para ficar mais legível (ex: 'nome_completo' vira 'Nome Completo')
            formatted_key = key.replace('_', ' ').title()
            pdf.cell(0, 10, f"{formatted_key}:", 0, 1)
            pdf.set_font("Arial", '', 12)
            # Usa multi_cell para que textos longos quebrem a linha
            pdf.multi_cell(0, 10, str(value))
            pdf.ln(5)

    temp_dir = "/tmp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    file_path = os.path.join(temp_dir, f"curriculo_{resume_data.get('phone', 'temp')}.pdf")
    pdf.output(file_path)
    return file_path

def generate_dynamic_pix(price, description):
    if not all([PIX_RECIPIENT_NAME, PIX_CITY, PIX_KEY]):
        print("ERRO: Dados do PIX não configurados nas variáveis de ambiente.")
        return "ERRO_CONFIG_PIX"
    try:
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price, description=description)
        return pix.get_br_code()
    except Exception as e:
        print(f"Erro ao gerar PIX: {e}")
        return "ERRO_GERACAO_PIX"

# ==============================================================================
# --- MÁQUINA DE ESTADOS COMPLETA
# ==============================================================================
conversation_flow = {
    'awaiting_welcome': {'question': f"Olá! Eu sou o {BOT_NAME}, seu assistente para criação de currículos. Vamos começar? (responda com *sim*)", 'next_state': 'collecting_name'},
    'collecting_name': {'question': 'Qual o seu nome completo?', 'key': 'nome_completo', 'next_state': 'collecting_email'},
    'collecting_email': {'question': 'Ótimo! Agora, qual o seu melhor e-mail?', 'key': 'email', 'next_state': 'collecting_phone'},
    'collecting_phone': {'question': 'E o seu telefone com DDD?', 'key': 'telefone', 'next_state': 'collecting_experience'},
    'collecting_experience': {'question': 'Perfeito. Para finalizar, descreva sua experiência profissional mais relevante.', 'key': 'experiencia', 'next_state': 'awaiting_payment'},
}

def process_message(phone, message):
    user = get_user(phone)
    if not user:
        user = create_user(phone)

    state = user['state']
    
    # Lógica para a primeira saudação
    if state == 'awaiting_welcome':
        if 'sim' in message.lower():
            next_state_info = conversation_flow[conversation_flow[state]['next_state']]
            send_whatsapp_message(phone, next_state_info['question'])
            update_user_state(phone, conversation_flow[state]['next_state'])
        else:
            send_whatsapp_message(phone, conversation_flow[state]['question'])
        return

    # Lógica para os outros passos da conversa
    if state in conversation_flow:
        step_info = conversation_flow[state]
        
        # Salva o dado da etapa atual
        update_resume_data(phone, {step_info['key']: message})
        
        next_state = step_info['next_state']
        
        if next_state == 'awaiting_payment':
            pix_code = generate_dynamic_pix(PLANO_BASICO_PRECO, "Currículo Profissional")
            if "ERRO" in pix_code:
                send_whatsapp_message(phone, "Concluímos a coleta de dados! No momento, estamos com uma instabilidade no sistema de pagamento. Por favor, tente novamente mais tarde.")
            else:
                send_whatsapp_message(phone, f"Excelente, dados coletados! Para receber seu currículo em PDF, faça o pagamento de R${PLANO_BASICO_PRECO:.2f} usando o Pix Copia e Cola abaixo:")
                send_whatsapp_message(phone, pix_code)
                send_whatsapp_message(phone, "Após pagar, basta digitar 'pago' aqui para eu confirmar e te enviar o arquivo.")
            update_user_state(phone, 'awaiting_payment_confirmation')
        else:
            # Envia a próxima pergunta
            next_question = conversation_flow[next_state]['question']
            send_whatsapp_message(phone, next_question)
            update_user_state(phone, next_state)
            
    elif state == 'awaiting_payment_confirmation':
        if 'pago' in message.lower():
            # Em uma versão futura, aqui entraria a verificação do comprovante com IA
            send_whatsapp_message(phone, "Ótimo! Confirmação recebida! Estou gerando seu currículo em PDF e já te envio.")
            resume_data = json.loads(user['resume_data'])
            resume_data['phone'] = phone # Adiciona o telefone para o nome do arquivo
            
            pdf_path = generate_resume_pdf(resume_data)
            
            send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo', 'user').split(' ')[0]}.pdf")
            os.remove(pdf_path) # Limpa o arquivo temporário do servidor
            
            send_whatsapp_message(phone, "Currículo enviado! Muito obrigado e boa sorte na sua busca! 🚀")
            update_user_state(phone, 'completed')
        else:
            send_whatsapp_message(phone, "Ainda estou aguardando a sua confirmação. Assim que o pagamento for efetuado, é só me avisar digitando 'pago'.")

# ==============================================================================
# --- ROTA DE WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        data = request.json
        print("--> Webhook Recebido:", json.dumps(data, indent=2))
        
        phone = data.get('phone')
        message = data.get('text', {}).get('message', '').strip()

        if phone and message:
            print(f"-> Mensagem processada de {phone}: '{message}'")
            # Garante que o usuário exista antes de processar
            user = get_user(phone)
            if not user:
                create_user(phone)
            
            process_message(phone, message)
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"### ERRO CRÍTICO NO WEBHOOK: {e} ###")
        return jsonify({"status": "error", "message": "Erro interno no servidor"}), 500

# ==============================================================================
# --- BLOCO DE EXECUÇÃO LOCAL (IGNORADO PELO RENDER)
# ==============================================================================
if __name__ == '__main__':
    print("-> Servidor sendo executado em modo de desenvolvimento local (debug).")
    app.run(host='0.0.0.0', port=8080, debug=True)
