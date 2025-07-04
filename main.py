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
from bs4 import BeautifulSoup
import google.generativeai as genai
import openai

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- CONFIGURAÇÕES DE API E CHAVES (VIA VARIÁVEIS DE AMBIENTE) ---
openai.api_key = os.environ.get('OPENAI_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')

# --- CONFIGURAÇÕES DO BOT DE CURRÍCULO ---
PIX_RECIPIENT_NAME = os.environ.get('PIX_RECIPIENT_NAME', "Seu Nome Completo Aqui")
PIX_CITY = os.environ.get('PIX_CITY', "SUA CIDADE AQUI")
PIX_KEY = os.environ.get('PIX_KEY')

PLANO_BASICO_PRECO = 5.99
PLANO_PREMIUM_PRECO = 10.99

# --- CAMINHOS DE ARQUIVOS PARA AMBIENTE DE PRODUÇÃO (RENDER) ---
# Render oferece um disco persistente em /var/data
# Você precisa criar um "Disk" no painel do Render com o Mount Path /var/data
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')
DATABASE_FILE = os.path.join(DATA_DIR, 'bot_database.db')
FONT_DIR = DATA_DIR # Salvar fontes no disco persistente também

TEMPLATES = {
    '1': {'name': 'Profissional Clássico', 'image_url': 'https://i.imgur.com/wA5g2hN.png'},
    '2': {'name': 'Moderno com Coluna', 'image_url': 'https://i.imgur.com/uN1mU7A.png'},
    '3': {'name': 'Criativo com Ícones', 'image_url': 'https://i.imgur.com/vPkL3uD.png'},
    '4': {'name': 'Minimalista Elegante', 'image_url': 'https://i.imgur.com/Y1Q8Z3s.png'},
    '5': {'name': 'Executivo de Impacto', 'image_url': 'https://i.imgur.com/nJ6B6gB.png'}
}

# --- INICIALIZAÇÃO ROBUSTA (PARA FUNCIONAR COM GUNICORN NO RENDER) ---
def init_database():
    print("-> Verificando e inicializando o banco de dados...")
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY, state TEXT, resume_data TEXT,
            plan TEXT, paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reminder_sent INTEGER DEFAULT 0 
        )
    ''')
    conn.commit()
    conn.close()
    print("   Banco de dados pronto.")

def download_fonts():
    font_path = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
    font_bold_path = os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')
    if not os.path.exists(font_path):
        print("-> Baixando a fonte DejaVu para suporte a ícones...")
        try:
            url_font = "https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans.ttf?raw=true"
            r = requests.get(url_font, timeout=15)
            r.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(r.content)

            url_bold = "https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans-Bold.ttf?raw=true"
            r_bold = requests.get(url_bold, timeout=15)
            r_bold.raise_for_status()
            with open(font_bold_path, 'wb') as f:
                f.write(r_bold.content)
            
            print("   Fonte baixada com sucesso.")
        except requests.exceptions.RequestException as e:
            print(f"   AVISO: O download da fonte falhou: {e}. O bot continuará sem os ícones.")
    else:
        print("-> Fonte DejaVu já existe.")

# Executa a inicialização quando o módulo é carregado
init_database()
download_fonts()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
if openai.api_key:
    # Apenas para confirmar que a chave foi lida
    pass

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
    cursor.execute('''
        INSERT OR REPLACE INTO users (phone, state, resume_data, reminder_sent) 
        VALUES (?, ?, ?, 0)
    ''', (phone, 'awaiting_welcome', json.dumps({})))
    conn.commit()
    conn.close()
    return get_user(phone)

def update_user_state(phone, state):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ?, updated_at = ? WHERE phone = ?", (state, datetime.now(), phone))
    conn.commit()
    conn.close()

def update_resume_data(phone, new_data_dict):
    user = get_user(phone)
    if not user: return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data_dict)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET resume_data = ?, updated_at = ? WHERE phone = ?", (json.dumps(resume_data), datetime.now(), phone))
    conn.commit()
    conn.close()

def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Z-API Erro ao enviar mensagem: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Erro de conexão ao enviar mensagem Z-API: {e}")
        return None

def generate_resume_pdf(resume_data):
    # Lógica completa de geração de PDF...
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, value in resume_data.items():
        pdf.multi_cell(0, 10, f"{key}: {value}")
    
    temp_dir = "/tmp" # Diretório temporário seguro para escrita
    file_path = os.path.join(temp_dir, f"curriculo_{resume_data.get('phone', 'user')}.pdf")
    pdf.output(file_path)
    return file_path

def generate_dynamic_pix(price, description):
    if not all([PIX_RECIPIENT_NAME, PIX_CITY, PIX_KEY]):
        return "ERRO_CONFIG_PIX"
    try:
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price, description=description)
        return pix.get_br_code()
    except Exception as e:
        print(f"Erro ao gerar PIX: {e}")
        return "ERRO_GERACAO_PIX"

# ==============================================================================
# --- MÁQUINA DE ESTADOS PRINCIPAL
# ==============================================================================
conversation_flow = {
    'awaiting_welcome': {'question': f"Olá! Eu sou o {BOT_NAME}, seu assistente para criação de currículos. Vamos começar? (responda 'sim')", 'next_state': 'collecting_name'},
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
    
    if state in conversation_flow:
        step_info = conversation_flow[state]
        
        if 'key' in step_info:
            update_resume_data(phone, {step_info['key']: message})
        
        next_state = step_info['next_state']
        
        if next_state == 'awaiting_payment':
            pix_code = generate_dynamic_pix(PLANO_BASICO_PRECO, "Currículo Profissional")
            if "ERRO" in pix_code:
                send_whatsapp_message(phone, "Concluímos a coleta de dados! No momento, estamos com uma instabilidade no sistema de pagamento. Por favor, tente novamente mais tarde.")
            else:
                send_whatsapp_message(phone, f"Excelente, dados coletados! Para receber seu currículo em PDF, faça o pagamento de R$ {PLANO_BASICO_PRECO:.2f} usando o Pix Copia e Cola abaixo:")
                send_whatsapp_message(phone, pix_code)
                send_whatsapp_message(phone, "Após pagar, basta digitar 'pago' aqui para eu confirmar e te enviar o arquivo.")
            update_user_state(phone, 'awaiting_payment_confirmation')
        else:
            next_question = conversation_flow[next_state]['question']
            send_whatsapp_message(phone, next_question)
            update_user_state(phone, next_state)
            
    elif state == 'awaiting_payment_confirmation':
        if 'pago' in message.lower():
            send_whatsapp_message(phone, "Confirmação recebida! Estou gerando seu currículo em PDF, só um momento...")
            resume_data = json.loads(user['resume_data'])
            resume_data['phone'] = phone
            pdf_path = generate_resume_pdf(resume_data)
            
            send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo', 'user')}.pdf")
            os.remove(pdf_path) # Limpa o arquivo temporário
            
            send_whatsapp_message(phone, "Currículo enviado! Muito obrigado e boa sorte! 🚀")
            update_user_state(phone, 'completed')
        else:
            send_whatsapp_message(phone, "Ainda estou no aguardo da sua confirmação. Assim que o pagamento for efetuado, é só me avisar digitando 'pago'.")

# ==============================================================================
# --- ROTA DE WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        data = request.json
        print("--> Webhook Recebido:", json.dumps(data, indent=2))
        
        phone = None
        message = ""

        # Lida com diferentes formatos de payload da Z-API
        if 'phone' in data:
            phone = data['phone']
        
        if 'text' in data and isinstance(data['text'], str):
            message = data['text'].strip()
        elif 'text' in data and isinstance(data['text'], dict) and 'message' in data['text']:
            message = data['text']['message'].strip()
        elif 'message' in data and isinstance(data['message'], str):
             message = data['message'].strip()

        if phone and message:
            print(f"-> Mensagem processada de {phone}: '{message}'")
            process_message(phone, message)
        else:
            print(f"-> Payload recebido sem 'phone' ou 'text' válidos.")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"### ERRO CRÍTICO NO WEBHOOK: {e} ###")
        return jsonify({"status": "error", "message": "Erro interno no servidor"}), 500

# ==============================================================================
# --- BLOCO DE EXECUÇÃO LOCAL (IGNORADO PELO RENDER)
# ==============================================================================
if __name__ == '__main__':
    print("-> Servidor sendo executado em modo de desenvolvimento local (debug).")
    # No modo local, o Gunicorn não é usado, então o app.run é executado.
    app.run(host='0.0.0.0', port=8080, debug=True)
