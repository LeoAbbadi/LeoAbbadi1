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

# ==============================================================================
# --- INICIALIZAÇÃO ROBUSTA (PARA GUNICORN NO RENDER)
# ==============================================================================
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
        except requests.exceptions.RequestException as e:
            print(f"   AVISO: O download da fonte falhou: {e}. Ícones podem não funcionar.")
        except Exception as e:
            print(f"   AVISO: Um erro inesperado ocorreu durante o download da fonte: {e}")
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
# --- CLASSES E FUNÇÕES CORE
# ==============================================================================

class PDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

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
        print(f"Erro de conexão ao enviar imagem Z-API: {e}")

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

def correct_text_with_ia(text):
    if not text or not GEMINI_API_KEY: return text
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Corrija a gramática, ortografia e o uso de letras maiúsculas do texto a seguir para um padrão profissional, mantendo o significado original. Responda apenas com o texto corrigido.\n\nTexto original: '{text}'")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro na correção com IA: {e}")
        return text

def translate_resume_with_ia(resume_data):
    if not GEMINI_API_KEY: return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Traduza os valores do seguinte objeto JSON de português para inglês. Mantenha as chaves (keys) do JSON exatamente iguais. Responda apenas com o objeto JSON traduzido.\n\nJSON Original: {json.dumps(resume_data, indent=2)}")
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Erro na tradução com IA: {e}")
        return None

def verify_payment_receipt(image_url):
    if not GEMINI_API_KEY: return True
    try:
        model = genai.GenerativeModel('gemini-pro-vision')
        image_response = requests.get(image_url)
        image_parts = [{"mime_type": image_response.headers['Content-Type'], "data": image_response.content}]
        prompt = "Analise a imagem. É um comprovante PIX válido? Responda apenas 'SIM' ou 'NAO'."
        response = model.generate_content([prompt, *image_parts])
        return "SIM" in response.text.upper()
    except Exception as e:
        print(f"Erro na verificação de pagamento com Gemini: {e}")
        return False

def generate_resume_pdf(resume_data, template_choice="1"):
    pdf = PDF('P', 'mm', 'A4')
    font_path = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
    font_bold_path = os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf')
    try:
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.add_font('DejaVu', 'B', font_bold_path, uni=True)
        FONT_FAMILY = 'DejaVu'
    except RuntimeError:
        FONT_FAMILY = 'Arial'

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def get_data(key, default='Não informado'):
        return resume_data.get(key, default)

    def draw_entry(title, subtitle, description):
        pdf.set_font(FONT_FAMILY, 'B', 12)
        pdf.multi_cell(0, 6, title)
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, subtitle)
        pdf.ln(1)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(FONT_FAMILY, '', 11)
        pdf.multi_cell(0, 6, description)
        pdf.ln(4)
        
    # Implementação dos modelos de PDF
    if template_choice == '1': # Profissional Clássico
        pdf.set_font(FONT_FAMILY, 'B', 22)
        pdf.multi_cell(0, 12, get_data('nome_completo').upper(), 0, 'C')
        pdf.set_font(FONT_FAMILY, '', 11)
        info_line = f"{get_data('idade')} anos | {get_data('endereco')} | {get_data('contato')}"
        pdf.cell(0, 8, info_line, 0, 1, 'C')
        pdf.ln(10)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        def section_title(title):
            pdf.set_font(FONT_FAMILY, 'B', 14)
            pdf.cell(0, 10, title.upper(), 0, 1, 'L')
        
        section_title("Objetivo")
        pdf.set_font(FONT_FAMILY, '', 11)
        pdf.multi_cell(0, 6, get_data('cargo_desejado'))
        section_title("Formação")
        pdf.set_font(FONT_FAMILY, '', 11)
        pdf.multi_cell(0, 6, get_data('escolaridade'))
        section_title("Experiência Profissional")
        for exp in get_data('experiencias', []):
            draw_entry(exp.get('cargo'), exp.get('periodo'), exp.get('descricao'))
        section_title("Habilidades")
        pdf.set_font(FONT_FAMILY, '', 11)
        pdf.multi_cell(0, 6, get_data('habilidades'))
        section_title("Cursos Adicionais")
        for curso in get_data('cursos', []):
            pdf.set_font(FONT_FAMILY, '', 11)
            pdf.multi_cell(0, 6, f"- {curso}")
    
    # Adicionar aqui a lógica para os templates 2 e 3...

    temp_path = os.path.join(TEMP_DIR, f"curriculo_{get_data('phone', 'user')}.pdf")
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

def extract_name(text):
    phrases_to_remove = ["meu nome é", "me chamo"]
    text_lower = text.lower()
    for phrase in phrases_to_remove:
        if text_lower.startswith(phrase):
            return text[len(phrase):].strip()
    return text

def validate_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)

def validate_phone(phone):
    return len(re.findall(r'\d', phone)) >= 10

# ==============================================================================
# --- MÁQUINA DE ESTADOS E HANDLERS
# ==============================================================================
conversation_flow = {
    'collecting_name': {'question': 'Para começar, qual o seu nome completo?', 'key': 'nome_completo', 'next_state': 'collecting_email'},
    'collecting_email': {'question': 'Ótimo, {user_name}! Agora, qual o seu melhor e-mail para contato?', 'key': 'email', 'next_state': 'collecting_phone', 'validation': validate_email},
    'collecting_phone': {'question': 'E o seu telefone com DDD?', 'key': 'telefone', 'next_state': 'collecting_address', 'validation': validate_phone},
    'collecting_address': {'question': 'Qual seu endereço? (Cidade, Estado)', 'key': 'endereco', 'next_state': 'collecting_education'},
    'collecting_education': {'question': 'Qual o seu nível de escolaridade? (Ex: Ensino Médio Completo, Superior Cursando em...)', 'key': 'escolaridade', 'next_state': 'collecting_experience_start'},
    'collecting_skills': {'question': 'Quais são suas principais habilidades e competências? (Ex: Comunicação, Pacote Office, etc.)', 'key': 'habilidades', 'next_state': 'collecting_courses_start'},
}

def process_message(phone, message):
    user = get_user(phone)
    if not user: user = create_user(phone)

    state = user['state']
    resume_data = json.loads(user['resume_data'])

    # Comandos universais
    if message.lower() in ['reiniciar', 'cancelar']:
        create_user(phone)
        send_whatsapp_message(phone, "Ok, vamos recomeçar do zero. Quando estiver pronto, é só me mandar um 'oi'.")
        return

    # Fluxo principal
    if state == 'awaiting_welcome':
        handle_introduction(phone)
        return

    elif state == 'awaiting_start_confirmation':
        if any(word in message.lower() for word in ['sim', 's', 'vamos', 'começar']):
            next_state = 'collecting_name'
            question = conversation_flow[next_state]['question']
            send_whatsapp_message(phone, question)
            update_user_state(phone, next_state)
        else:
            send_whatsapp_message(phone, "Tudo bem! Fico por aqui caso mude de ideia. É só mandar um 'oi' para começar. 😉")
        return
        
    elif state in conversation_flow:
        step_info = conversation_flow[state]
        
        # Validação
        if 'validation' in step_info and not step_info['validation'](message):
            send_whatsapp_message(phone, f"Hmm, essa informação parece inválida. Poderia tentar novamente?\n\n{step_info['question']}")
            return

        # Correção com IA
        corrected_message = correct_text_with_ia(message)
        update_resume_data(phone, {step_info['key']: corrected_message})
        
        next_state = step_info['next_state']
        question = conversation_flow.get(next_state, {}).get('question')
        
        user_name = resume_data.get('nome_completo', 'tudo bem?').split(' ')[0]
        if question:
            send_whatsapp_message(phone, question.format(user_name=user_name))
        
        update_user_state(phone, next_state)
        # Se o próximo estado for um loop, chama a si mesmo para iniciar o loop
        if next_state.endswith('_start'):
            process_message(phone, "") # Passa uma mensagem vazia para iniciar o novo fluxo
        return
        
    # ... (Lógica para os loops de experiência, cursos, revisão, pagamento, etc.) ...
    
def process_image_message(phone, image_url):
    # Lógica de processar comprovante
    pass
    
def handle_introduction(phone):
    send_whatsapp_message(phone, f"Olá! 👋 Eu sou o {BOT_NAME}, seu assistente de carreira digital.")
    plan_message = (
        "Comigo, você pode criar um currículo de impacto em minutos. Veja nossos planos:\n\n"
        f"1️⃣ *Plano Básico (R$ {PLANO_BASICO_PRECO:.2f}):* Seu currículo em PDF em um de nossos modelos profissionais.\n\n"
        f"2️⃣ *Plano Premium (R$ {PLANO_PREMIUM_PRECO:.2f}):* Tudo do básico + Versão do seu currículo em Inglês."
    )
    send_whatsapp_message(phone, plan_message)
    send_whatsapp_message(phone, "Estes são nossos modelos de design:")
    for tid, tinfo in TEMPLATES.items():
        send_whatsapp_image(phone, tinfo['image_url'], f"*Modelo {tid}:* {tinfo['name']}")
    send_whatsapp_message(phone, "Gostou? Se quiser começar a criar seu currículo agora, é só dizer *'sim'*!")
    update_user_state(phone, 'awaiting_start_confirmation')

# ==============================================================================
# --- ROTA DE WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        data = request.json
        print("--> Webhook Recebido:", json.dumps(data, indent=2))
        phone = data.get('phone')
        if not phone: return jsonify({"status": "ok"}), 200

        user = get_user(phone)
        if not user: user = create_user(phone)
        else: db_update("UPDATE users SET updated_at = ? WHERE phone = ?", (datetime.now(), phone))
        
        message_text = data.get('text', {}).get('message', '').strip()
        is_image = 'url' in data and data.get('mimetype', '').startswith('image')

        if is_image:
            process_image_message(phone, data['url'])
        elif message_text or user['state'] == 'awaiting_welcome': # Processa mesmo se a primeira mensagem for vazia
            process_message(phone, message_text)
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"### ERRO CRÍTICO NO WEBHOOK: {e} ###")
        return jsonify({"status": "error"}), 500

# ==============================================================================
# --- BLOCO DE EXECUÇÃO LOCAL
# ==============================================================================
if __name__ == '__main__':
    print("-> Servidor sendo executado em modo de desenvolvimento local.")
    app.run(host='0.0.0.0', port=8080, debug=True)
