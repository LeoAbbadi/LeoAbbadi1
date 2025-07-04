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
import google.generativeai as genai

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- CAMINHOS DE ARQUIVOS ---
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')
DATABASE_FILE = os.path.join(DATA_DIR, 'bot_database.db')
FONT_DIR = DATA_DIR
TEMP_DIR = "/tmp"

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
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

init_database()

# --- CHAVES E CONFIGS ---
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')
PIX_RECIPIENT_NAME = os.environ.get('PIX_RECIPIENT_NAME', "Seu Nome")
PIX_CITY = os.environ.get('PIX_CITY', "Cidade")
PIX_KEY = os.environ.get('PIX_KEY')
PLANO_BASICO_PRECO = 5.99

# ==============================================================================
# --- FUNÇÕES DO BOT
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
    cursor.execute("""
        INSERT OR REPLACE INTO users (phone, state, resume_data)
        VALUES (?, ?, ?)
    """, (phone, 'awaiting_welcome', json.dumps({})))
    conn.commit()
    conn.close()
    return get_user(phone)

def update_user_state(phone, state):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ? WHERE phone = ?", (state, phone))
    conn.commit()
    conn.close()

def update_resume_data(phone, new_data):
    user = get_user(phone)
    if not user: return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET resume_data = ? WHERE phone = ?", (json.dumps(resume_data), phone))
    conn.commit()
    conn.close()

def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    requests.post(url, json=payload, headers=headers)

def send_whatsapp_document(phone, doc_path, filename):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    requests.post(url, json=payload, headers=headers)

def generate_dynamic_pix(price, description):
    try:
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price, description=description)
        return pix.get_br_code()
    except Exception as e:
        return "ERRO_PIX"

def generate_resume_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, data.get('nome_completo', 'Currículo'), 0, 1, 'C')
    pdf.ln(5)
    
    campos = [
        ('Idade', 'idade'),
        ('Cidade/Estado', 'cidade_estado'),
        ('Telefone', 'telefone'),
        ('Email', 'email'),
        ('Cargo desejado', 'cargo'),
        ('Formacao', 'formacao'),
        ('Cursos Extras', 'cursos'),
        ('Experiências', 'experiencias'),
        ('Habilidades', 'habilidades'),
        ('Disponibilidade', 'disponibilidade')
    ]

    for label, key in campos:
        valor = data.get(key)
        if valor:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"{label}:", 0, 1)
            pdf.set_font("Arial", '', 12)
            pdf.multi_cell(0, 10, str(valor))
            pdf.ln(3)

    path = os.path.join(TEMP_DIR, f"curriculo_{data.get('phone', 'user')}.pdf")
    pdf.output(path)
    return path

# ==============================================================================
# --- FLUXO DO BOT / CONVERSA / LOOP ---
# ==============================================================================
flow = [
    ('nome_completo', 'Primeiro, qual seu nome completo?'),
    ('idade', 'Qual sua idade?'),
    ('cidade_estado', 'Em que cidade e estado você mora?'),
    ('telefone', 'Nos diga seu telefone com DDD.'),
    ('email', 'Qual seu e-mail?'),
    ('cargo', 'Qual área ou cargo você busca?'),
    ('formacao', 'Qual sua formação escolar?'),
    ('cursos', 'Deseja adicionar cursos extras? (Envie 1 por vez e digite OK quando terminar)'),
    ('experiencias', 'Conte suas experiências profissionais (uma por vez e digite OK quando terminar)'),
    ('habilidades', 'Liste habilidades ou conhecimentos (Ex: pacote Office, vendas, atendimento...)'),
    ('disponibilidade', 'Qual sua disponibilidade (ex: manhã, tarde, início imediato...)')
]

user_loops = {}

# ==============================================================================
# --- LÓGICA PRINCIPAL
# ==============================================================================
def process_message(phone, message):
    user = get_user(phone) or create_user(phone)
    state = user['state']
    resume_data = json.loads(user['resume_data'])

    if state == 'awaiting_welcome':
        if message.lower().strip() in ['sim', 'começar', 'ok']:
            update_user_state(phone, flow[0][0])
            send_whatsapp_message(phone, flow[0][1])
        else:
            send_whatsapp_message(phone, f"Olá! Eu sou o {BOT_NAME}, seu assistente para criar currículos em PDF direto aqui no WhatsApp. Deseja começar? (Responda com *sim*)")
        return

    keys = [k for k, _ in flow]
    if state in keys:
        idx = keys.index(state)
        key, _ = flow[idx]

        # LOOP para cursos/experiências
        if key in ['cursos', 'experiencias']:
            if message.lower().strip() == 'ok':
                next_state = keys[idx+1]
                update_user_state(phone, next_state)
                send_whatsapp_message(phone, flow[idx+1][1])
                return

            entradas = resume_data.get(key, [])
            entradas.append(message)
            update_resume_data(phone, {key: entradas})
            send_whatsapp_message(phone, f"{key[:-1].capitalize()} adicionado. Envie outro ou digite *OK* para finalizar.")
            return

        else:
            update_resume_data(phone, {key: message})
            if idx+1 < len(flow):
                next_state = keys[idx+1]
                update_user_state(phone, next_state)
                send_whatsapp_message(phone, flow[idx+1][1])
            else:
                # FIM DO FLUXO
                pix_code = generate_dynamic_pix(PLANO_BASICO_PRECO, "Pagamento do Currículo")
                send_whatsapp_message(phone, f"Estamos quase lá! Para gerar seu PDF, envie R$ {PLANO_BASICO_PRECO:.2f} via PIX:")
                send_whatsapp_message(phone, pix_code)
                send_whatsapp_message(phone, "Depois de pagar, responda com *pago*. Se quiser como cortesia, digite *gerar*. ")
                update_user_state(phone, 'awaiting_payment')
        return

    if state == 'awaiting_payment':
        if message.lower().strip() in ['pago', 'gerar']:
            pdf_path = generate_resume_pdf(resume_data)
            send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo', 'user')}.pdf")
            send_whatsapp_message(phone, "Currículo enviado! Obrigado por usar o bot do Cadu. Boa sorte!")
            os.remove(pdf_path)
            update_user_state(phone, 'completed')
        else:
            send_whatsapp_message(phone, "Mensagem não reconhecida. Digite *pago* ou *gerar* para continuar.")

# ==============================================================================
# --- WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('text', {}).get('message', '')
        if phone and message:
            process_message(phone, message)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({'status': 'error'})

# ==============================================================================
# --- EXECUÇÃO LOCAL
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True, port=8080)

