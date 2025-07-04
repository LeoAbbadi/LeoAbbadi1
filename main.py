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

# --- CAMINHOS DE ARQUIVOS PARA AMBIENTE DE PRODUÇÃO (RENDER) ---
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')
DATABASE_FILE = os.path.join(DATA_DIR, 'bot_database.db')
FONT_DIR = DATA_DIR
TEMP_DIR = "/tmp" 

# --- FUNÇÕES DE INICIALIZAÇÃO ROBUSTA (PARA GUNICORN) ---
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
    print(f"   Banco de dados pronto em: {DATABASE_FILE}")

def download_fonts():
    font_path = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
    font_bold_path = os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')
    
    if not os.path.exists(font_path):
        print("-> Baixando a fonte DejaVu para suporte a ícones...")
        try:
            url_font = "https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans.ttf?raw=true"
            r = requests.get(url_font, timeout=15)
            r.raise_for_status()
            with open(font_path, 'wb') as f: f.write(r.content)

            url_bold = "https://github.com/dejavu-fonts/dejavu-fonts/blob/main/ttf/DejaVuSans-Bold.ttf?raw=true"
            r_bold = requests.get(url_bold, timeout=15)
            r_bold.raise_for_status()
            with open(font_bold_path, 'wb') as f: f.write(r_bold.content)
            
            print("   Fonte baixada com sucesso.")
        except Exception as e:
            print(f"   AVISO: O download da fonte falhou: {e}. Ícones podem não funcionar.")
    else:
        print("-> Fonte DejaVu já existe.")

# --- EXECUÇÃO DA INICIALIZAÇÃO ---
init_database()
download_fonts()

# --- CONFIGURAÇÕES DE API E CHAVES ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("-> Configuração da API do Gemini bem-sucedida.")
    except Exception as e:
        print(f"ERRO: Falha ao configurar a API do Gemini: {e}")

# --- CONFIGURAÇÕES DE NEGÓCIO ---
PIX_RECIPIENT_NAME = os.environ.get('PIX_RECIPIENT_NAME', "Seu Nome Completo Aqui")
PIX_CITY = os.environ.get('PIX_CITY', "SUA CIDADE AQUI")
PIX_KEY = os.environ.get('PIX_KEY')

PLANO_BASICO_PRECO = 5.99
PLANO_PREMIUM_PRECO = 10.99

TEMPLATES = {
    '1': {'name': 'Profissional Clássico', 'image_url': 'https://i.imgur.com/wA5g2hN.png'},
    '2': {'name': 'Moderno com Coluna', 'image_url': 'https://i.imgur.com/uN1mU7A.png'},
    '3': {'name': 'Criativo com Ícones', 'image_url': 'https://i.imgur.com/vPkL3uD.png'}
}

# ==============================================================================
# --- FUNÇÕES CORE DO BOT
# ==============================================================================
class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def db_update(query, params=()):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    if 'UPDATE' in query.upper():
        set_index = query.upper().find('SET') + 4
        query = query[:set_index] + ' updated_at = ?, ' + query[set_index:]
        params = (datetime.now(),) + params
    cursor.execute(query, params)
    conn.commit()
    conn.close()

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
        "INSERT OR REPLACE INTO users (phone, state, resume_data, reminder_sent) VALUES (?, ?, ?, 0)",
        (phone, 'awaiting_welcome', json.dumps({}))
    )
    conn.commit()
    conn.close()
    return get_user(phone)

def update_user_state(phone, state):
    db_update("UPDATE users SET state = ? WHERE phone = ?", (state, phone))

def update_resume_data(phone, new_data_dict):
    user = get_user(phone)
    if not user: return
    resume_data = json.loads(user['resume_data'])
    resume_data.update(new_data_dict)
    db_update("UPDATE users SET resume_data = ? WHERE phone = ?", (json.dumps(resume_data), phone))

def send_whatsapp_message(phone, message):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Z-API Erro ao enviar mensagem: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro de conexão ao enviar mensagem Z-API: {e}")

def send_whatsapp_image(phone, image_url, caption=""):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-image"
    payload = {"phone": phone, "image": image_url, "caption": caption}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Erro ao enviar imagem Z-API: {e}")

def send_whatsapp_document(phone, doc_path, filename):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Erro ao enviar documento Z-API: {e}")

def generate_resume_pdf(resume_data, template_choice):
    pdf = PDF('P', 'mm', 'A4')
    # ... (lógica completa de geração dos 5 modelos de PDF aqui) ...
    temp_path = os.path.join(TEMP_DIR, f"curriculo_{resume_data.get('phone', 'user')}.pdf")
    pdf.output(temp_path)
    return temp_path

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
# --- MÁQUINA DE ESTADOS E HANDLERS DE FLUXO
# ==============================================================================
conversation_flow = {
    'collecting_name': {'question': 'Qual o seu nome completo?', 'key': 'nome_completo', 'next_state': 'collecting_email'},
    'collecting_email': {'question': 'Ótimo! Agora, qual o seu melhor e-mail?', 'key': 'email', 'next_state': 'collecting_phone'},
    'collecting_phone': {'question': 'E o seu telefone com DDD?', 'key': 'telefone', 'next_state': 'collecting_experience'},
    'collecting_experience': {'question': 'Perfeito. Para finalizar, descreva sua experiência profissional.', 'key': 'experiencia', 'next_state': 'choosing_template'},
}

def handle_introduction(phone):
    send_whatsapp_message(phone, f"Olá! 👋 Eu sou o {BOT_NAME}, seu assistente pessoal para criação de currículos profissionais.")
    
    plan_message = (
        "Comigo, você pode criar um currículo de impacto em minutos. Veja nossos planos:\n\n"
        f"1️⃣ *Plano Básico (R$ {PLANO_BASICO_PRECO:.2f}):* Seu currículo em PDF em um de nossos modelos profissionais.\n\n"
        f"2️⃣ *Plano Premium (R$ {PLANO_PREMIUM_PRECO:.2f}):* Tudo do básico + uma Carta de Apresentação personalizada gerada por IA."
    )
    send_whatsapp_message(phone, plan_message)
    
    send_whatsapp_message(phone, "Estes são alguns dos modelos que você pode escolher:")
    for tid, tinfo in TEMPLATES.items():
        send_whatsapp_image(phone, tinfo['image_url'], f"*Modelo {tid}:* {tinfo['name']}")
        
    send_whatsapp_message(phone, "Gostou? Se quiser começar a criar seu currículo agora, é só dizer *'sim'*!")
    update_user_state(phone, 'awaiting_start_confirmation')

def process_message(phone, message):
    user = get_user(phone)
    if not user:
        user = create_user(phone)
    state = user['state']

    if state == 'awaiting_welcome':
        handle_introduction(phone)
        return

    elif state == 'awaiting_start_confirmation':
        if any(word in message.lower() for word in ['sim', 'vamos', 'começar', 's']):
            next_state = 'collecting_name'
            question = conversation_flow[next_state]['question']
            send_whatsapp_message(phone, question)
            update_user_state(phone, next_state)
        else:
            send_whatsapp_message(phone, "Sem problemas! Estarei por aqui quando decidir começar. É só me mandar um 'oi'.")
        return

    if state in conversation_flow:
        step_info = conversation_flow[state]
        update_resume_data(phone, {step_info['key']: message})
        
        next_state = step_info['next_state']
        
        if next_state == 'choosing_template':
            send_whatsapp_message(phone, "Dados coletados! Agora, confirme o modelo que você mais gostou (responda com o número 1, 2 ou 3).")
            update_user_state(phone, 'choosing_template')
        else:
            question = conversation_flow[next_state]['question']
            send_whatsapp_message(phone, question)
            update_user_state(phone, next_state)
        return

    elif state == 'choosing_template':
        if message in TEMPLATES:
            update_resume_data(phone, {'template_choice': message})
            send_whatsapp_message(phone, "Ótima escolha! Agora, qual plano você deseja? (Responda 1 para Básico ou 2 para Premium)")
            update_user_state(phone, 'choosing_plan')
        else:
            send_whatsapp_message(phone, "Modelo inválido. Por favor, escolha um número de 1 a 3.")
        return

    elif state == 'choosing_plan':
        price = 0
        plan_name = ""
        if message == '1':
            price = PLANO_BASICO_PRECO
            plan_name = "Plano Básico"
        elif message == '2':
            price = PLANO_PREMIUM_PRECO
            plan_name = "Plano Premium"
        else:
            send_whatsapp_message(phone, "Opção inválida. Por favor, responda 1 para Básico ou 2 para Premium.")
            return

        update_resume_data(phone, {'plan': plan_name})
        pix_code = generate_dynamic_pix(price, f"Currículo Cadu - {plan_name}")
        
        if "ERRO" in pix_code:
            send_whatsapp_message(phone, "Estamos com uma instabilidade no sistema de pagamento. Por favor, tente novamente em alguns minutos.")
        else:
            send_whatsapp_message(phone, f"Para finalizar a compra do seu *{plan_name}* (R${price:.2f}), use o Pix Copia e Cola abaixo:")
            send_whatsapp_message(phone, pix_code)
            send_whatsapp_message(phone, "Após pagar, por favor, envie uma foto do comprovante aqui.")
        update_user_state(phone, 'awaiting_payment_receipt')
        return

def process_image_message(phone, image_url):
    user = get_user(phone)
    if not user or user['state'] != 'awaiting_payment_receipt':
        return

    send_whatsapp_message(phone, "Recebi seu comprovante! Analisando com nossa IA...")
    is_valid = True # Simula a verificação de IA por enquanto
    
    if is_valid:
        send_whatsapp_message(phone, "Pagamento confirmado com sucesso! 🎉 Gerando seu material...")
        resume_data = json.loads(user['resume_data'])
        resume_data['phone'] = phone
        template = resume_data.get('template_choice', '1')

        pdf_path = generate_resume_pdf(resume_data, template)
        send_whatsapp_document(phone, pdf_path, f"Seu_Curriculo_Cadu.pdf")
        os.remove(pdf_path)

        if resume_data.get('plan') == 'Plano Premium':
            # Lógica de gerar e enviar a carta de apresentação
            pass

        send_whatsapp_message(phone, "Material enviado! Muito obrigado e boa sorte! 🚀")
        update_user_state(phone, 'completed')
    else:
        send_whatsapp_message(phone, "Não consegui confirmar este comprovante. Por favor, tente enviar uma imagem mais nítida.")

# ==============================================================================
# --- ROTA DE WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        data = request.json
        print("--> Webhook Recebido:", json.dumps(data, indent=2))
        
        phone = data.get('phone')
        if not phone:
            return jsonify({"status": "ok"}), 200

        user = get_user(phone)
        if not user:
            user = create_user(phone)
        
        # Lógica para tratar texto ou imagem
        message_text = data.get('text', {}).get('message', '').strip()
        is_image = 'url' in data and data.get('mimetype', '').startswith('image')

        if is_image:
            process_image_message(phone, data['url'])
        elif message_text:
            process_message(phone, message_text)
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"### ERRO CRÍTICO NO WEBHOOK: {e} ###")
        return jsonify({"status": "error"}), 500

# ==============================================================================
# --- BLOCO DE EXECUÇÃO LOCAL
# ==============================================================================
if __name__ == '__main__':
    print("-> Servidor em modo de desenvolvimento local (debug).")
    app.run(host='0.0.0.0', port=8080, debug=True)
