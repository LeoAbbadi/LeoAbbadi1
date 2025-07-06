# -*- coding: utf-8 -*-

# ==============================================================================
# --- IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
# ==============================================================================
import os
import sqlite3
import json
import base64
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, request, jsonify
from fpdf import FPDF
from pypix import Pix
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

# Configuração do logging para ver o que o bot está fazendo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- CHAVES E CONFIGS VINDAS DO AMBIENTE (Render Secrets) ---
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Configuração da IA da Google (Gemini)
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    gemini_vision_model = genai.GenerativeModel('gemini-1.5-vision-pro')
    logging.info("API do Google Gemini configurada com sucesso.")
except Exception as e:
    logging.error(f"Falha ao configurar a API do Google: {e}")
    gemini_model = None
    gemini_vision_model = None

# --- CONFIGURAÇÕES DE PAGAMENTO ---
PIX_RECIPIENT_NAME = "Leonardo Maciel Abbadi"
PIX_CITY = "Brasilia"
PIX_PAYLOAD_STRING = "00020126580014br.gov.bcb.pix0136fd3412eb-9577-41ea-ba4d-12293570c0155204000053039865802BR5922Leonardo Maciel Abbadi6008Brasilia62240520daqr1894289448628220630439D1"
PRECO_BASICO = 9.99
PRECO_PREMIUM = 10.99
PRECO_REVISAO_HUMANA = 15.99

# --- CAMINHOS DE ARQUIVOS ---
DATA_DIR = os.environ.get('RENDER_DISK_PATH', '.')
DATABASE_FILE = os.path.join(DATA_DIR, 'cadu_database.db')
TEMP_DIR = "/tmp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# ==============================================================================
# --- BANCO DE DADOS (ARMAZENAMENTO DE DADOS DO USUÁRIO)
# ==============================================================================
def init_database():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            state TEXT,
            resume_data TEXT,
            plan TEXT DEFAULT 'none',
            template TEXT DEFAULT 'none',
            payment_verified INTEGER DEFAULT 0,
            last_interaction TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Banco de dados inicializado com sucesso.")

def get_user(phone):
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(phone, data):
    user = get_user(phone)
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    cursor = conn.cursor()
    if not user:
        initial_data = {
            'phone': phone, 'state': 'awaiting_welcome', 'resume_data': json.dumps({}),
            'plan': 'none', 'template': 'none', 'payment_verified': 0,
            'last_interaction': datetime.now()
        }
        initial_data.update(data)
        columns = ', '.join(initial_data.keys())
        placeholders = ', '.join('?' * len(initial_data))
        sql = f'INSERT INTO users ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, tuple(initial_data.values()))
    else:
        data['last_interaction'] = datetime.now()
        set_clause = ', '.join([f'{key} = ?' for key in data.keys()])
        values = list(data.values())
        values.append(phone)
        sql = f"UPDATE users SET {set_clause} WHERE phone = ?"
        cursor.execute(sql, tuple(values))
    conn.commit()
    conn.close()

# ==============================================================================
# --- FUNÇÕES DE COMUNICAÇÃO (WHATSAPP)
# ==============================================================================
def send_whatsapp_message(phone, message):
    logging.info(f"Enviando mensagem para {phone}: {message}")
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao enviar mensagem para {phone}: {e}")

def send_whatsapp_document(phone, doc_path, filename, caption=""):
    logging.info(f"Enviando documento {filename} para {phone}")
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {
        "phone": phone, "document": f"data:application/pdf;base64,{doc_base64}",
        "fileName": filename, "caption": caption
    }
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers, timeout=20)
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao enviar documento para {phone}: {e}")

# ==============================================================================
# --- FUNÇÕES DE INTELIGÊNCIA ARTIFICIAL (GEMINI)
# ==============================================================================
def get_ia_response(prompt):
    if not gemini_model: return "Desculpe, minha IA está temporariamente indisponível."
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Erro na API do Gemini: {e}")
        return "Tive um problema para processar sua resposta. Vamos tentar de novo."

def extract_info_from_message(question, user_message):
    prompt = f'Analise a conversa.\nPergunta: "{question}"\nResposta: "{user_message}"\n\nExtraia APENAS a informação principal da resposta, sem frases extras. Exemplo: se a pergunta é "Qual seu nome?" e a resposta é "meu nome é joão", extraia "joão".'
    return get_ia_response(prompt)

def analyze_pix_receipt(image_url):
    if not gemini_vision_model: return {'verified': False, 'reason': 'IA de visão indisponível.'}
    try:
        image_response = requests.get(image_url, timeout=15)
        image_response.raise_for_status()
        image_data = image_response.content
        prompt = f'Analise a imagem deste comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}" e a instituição é "Mercado Pago" ou "MercadoPago". Responda APENAS com JSON: {{"verified": true/false, "reason": "explicação breve"}}.'
        response = gemini_vision_model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': image_data}])
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        logging.error(f"Erro ao analisar comprovante PIX: {e}")
        return {'verified': False, 'reason': 'Não consegui ler a imagem do comprovante.'}

# ==============================================================================
# --- GERAÇÃO DE PDF (5 TEMPLATES)
# ==============================================================================
def clean_text_for_pdf(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_resume_pdf(data, template_choice):
    templates = {
        'classico': generate_template_classico, 'moderno': generate_template_moderno,
        'criativo': generate_template_criativo, 'minimalista': generate_template_minimalista,
        'tecnico': generate_template_tecnico
    }
    pdf_function = templates.get(template_choice, generate_template_classico)
    clean_data = {k: clean_text_for_pdf(str(v)) for k, v in data.items()}
    path = os.path.join(TEMP_DIR, f"curriculo_{data.get('phone', 'user')}.pdf")
    pdf_function(clean_data, path)
    return path

def generate_template_classico(data, path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, data.get('nome_completo', ''), 0, 1, 'C')
    pdf.set_font("Helvetica", '', 10)
    contato = f"{data.get('cidade_estado', '')} | {data.get('telefone', '')} | {data.get('email', '')}"
    pdf.cell(0, 10, contato, 0, 1, 'C')
    pdf.ln(10)
    def add_section(title, content):
        if content and content != '[]':
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 10, title.upper(), 0, 1, 'L')
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Helvetica", '', 10)
            pdf.multi_cell(0, 5, str(content).replace("['", "- ").replace("']", "").replace("', '", "\n- "))
            pdf.ln(5)
    add_section("Cargo Desejado", data.get('cargo'))
    add_section("Resumo Profissional", data.get('resumo'))
    add_section("Experiência Profissional", data.get('experiencias'))
    add_section("Formação Acadêmica", data.get('formacao'))
    add_section("Habilidades", data.get('habilidades'))
    add_section("Cursos e Certificações", data.get('cursos'))
    pdf.output(path)

def generate_template_moderno(data, path): generate_template_classico(data, path)
def generate_template_criativo(data, path): generate_template_classico(data, path)
def generate_template_minimalista(data, path): generate_template_classico(data, path)
def generate_template_tecnico(data, path): generate_template_classico(data, path)

# ==============================================================================
# --- FLUXO DA CONVERSA (STATE MACHINE)
# ==============================================================================
CONVERSATION_FLOW = [
    ('nome_completo', 'Legal! Para começar, qual o seu nome completo?'),
    ('cidade_estado', 'Ótimo, {nome}! Agora me diga em qual cidade e estado você mora.'),
    ('telefone', 'Pode me informar um telefone de contato com DDD?'),
    ('email', 'Qual o seu melhor e-mail para contato?'),
    ('cargo', 'Certo. Qual o cargo ou área que você está buscando?'),
    ('resumo', 'Escreva um pequeno resumo sobre você e seus objetivos. (Se não tiver, diga "pular").'),
    ('experiencias', 'Me conte sobre suas experiências profissionais. Envie uma de cada vez e digite "pronto" quando terminar.'),
    ('formacao', 'Qual a sua formação? (Ex: Ensino Médio Completo)'),
    ('habilidades', 'Liste suas principais habilidades, separando por vírgula.'),
    ('cursos', 'Tem cursos ou certificações? Envie um por um e digite "pronto" ao acabar.')
]
state_handlers = {}
def handle_state(state):
    def decorator(func):
        state_handlers[state] = func
        return func
    return decorator

def process_message(phone, message_data):
    user = get_user(phone)
    if not user:
        update_user(phone, {'state': 'awaiting_welcome'})
        user = get_user(phone)
    state = user['state']
    handler = state_handlers.get(state, handle_default)
    handler(user, message_data)

@handle_state('awaiting_welcome')
def handle_welcome(user, message_data):
    phone = user['phone']
    send_whatsapp_message(phone, f"Olá! Eu sou o {BOT_NAME} 🤖, seu assistente de carreira. Vou te ajudar a criar um currículo profissional incrível!")
    show_payment_options(phone)

def show_payment_options(phone):
    message = f"Para começarmos, conheça nossos planos:\n\n📄 *PLANO BÁSICO - R$ {PRECO_BASICO:.2f}*\n- Currículo em PDF em um dos nossos 5 templates.\n\n✨ *PLANO PREMIUM - R$ {PRECO_PREMIUM:.2f}*\n- Tudo do Básico, e mais:\n- Versão do currículo em Inglês.\n- Carta de apresentação profissional.\n\n👨‍💼 *REVISÃO HUMANA - R$ {PRECO_REVISAO_HUMANA:.2f}*\n- Tudo do Premium, e mais:\n- Revisão de um especialista de RH.\n\nDigite *básico*, *premium* ou *revisão* para escolher."
    send_whatsapp_message(phone, message)
    update_user(phone, {'state': 'awaiting_plan_choice'})

@handle_state('awaiting_plan_choice')
def handle_plan_choice(user, message_data):
    phone = user['phone']
    choice = message_data.get('text', '').lower().strip()
    plans = {'básico': 'basico', 'premium': 'premium', 'revisão': 'revisao_humana'}
    if choice in plans:
        plan_name = plans[choice]
        update_user(phone, {'plan': plan_name})
        template_message = "Ótima escolha! Agora, escolha o visual do seu currículo:\n\n1. *Clássico*\n2. *Moderno*\n3. *Criativo*\n4. *Minimalista*\n5. *Técnico*\n\nÉ só me dizer o número ou o nome."
        send_whatsapp_message(phone, template_message)
        update_user(phone, {'state': 'choosing_template'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Escolha *básico*, *premium* ou *revisão*.")

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone = user['phone']
    message = message_data.get('text', '').lower()
    template_map = {'1': 'classico', 'clássico': 'classico', '2': 'moderno', '3': 'criativo', '4': 'minimalista', '5': 'tecnico'}
    chosen_template = template_map.get(message, template_map.get(message.split(' ')[0]))
    if chosen_template:
        update_user(phone, {'template': chosen_template, 'state': 'flow_nome_completo'})
        send_whatsapp_message(phone, f"Perfeito! Vamos criar seu currículo no estilo *{chosen_template.capitalize()}*.")
        send_whatsapp_message(phone, CONVERSATION_FLOW[0][1])
    else:
        send_whatsapp_message(phone, "Não entendi. Diga o nome ou o número do template (1 a 5).")

def create_flow_handler(current_step_index):
    current_key, current_question = CONVERSATION_FLOW[current_step_index]
    @handle_state(f'flow_{current_key}')
    def flow_handler(user, message_data):
        phone = user['phone']
        message = message_data.get('text', '')
        resume_data = json.loads(user['resume_data'])
        is_list_field = current_key in ['experiencias', 'cursos']
        if is_list_field and message.lower().strip() in ['pronto', 'ok', 'finalizar']:
            go_to_next_step(phone, resume_data, current_step_index)
            return
        extracted_info = extract_info_from_message(current_question, message)
        if is_list_field:
            if current_key not in resume_data: resume_data[current_key] = []
            resume_data[current_key].append(extracted_info)
            send_whatsapp_message(phone, "Legal, adicionei! Pode me mandar o próximo ou digite *'pronto'*.")
        else:
            resume_data[current_key] = extracted_info
            go_to_next_step(phone, resume_data, current_step_index)
        update_user(phone, {'resume_data': json.dumps(resume_data)})
    def go_to_next_step(phone, resume_data, current_idx):
        if current_idx + 1 < len(CONVERSATION_FLOW):
            next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
            if '{nome}' in next_question:
                user_name = resume_data.get('nome_completo', '').split(' ')[0]
                next_question = next_question.format(nome=user_name)
            send_whatsapp_message(phone, next_question)
            update_user(phone, {'state': f'flow_{next_key}'})
        else:
            send_whatsapp_message(phone, "Ufa! Terminamos a coleta de dados. 💪")
            show_review_menu(phone, resume_data)
for i in range(len(CONVERSATION_FLOW)): create_flow_handler(i)

def show_review_menu(phone, resume_data):
    review_text = "Antes de finalizar, revise seus dados. Para corrigir, diga o número do item:\n\n"
    for i, (key, _) in enumerate(CONVERSATION_FLOW):
        review_text += f"*{i+1}. {key.replace('_', ' ').capitalize()}:* {resume_data.get(key, 'Não preenchido')}\n"
    review_text += "\nSe estiver tudo certo, digite *'finalizar'* para ir ao pagamento!"
    send_whatsapp_message(phone, review_text)
    update_user(phone, {'state': 'awaiting_review_choice'})

@handle_state('awaiting_review_choice')
def handle_review_choice(user, message_data):
    phone = user['phone']
    message = message_data.get('text', '').lower().strip()
    if message in ['finalizar', 'pagar', 'tudo certo', 'ok']:
        plan, price = user['plan'], 0.0
        prices = {'basico': PRECO_BASICO, 'premium': PRECO_PREMIUM, 'revisao_humana': PRECO_REVISAO_HUMANA}
        price = prices.get(plan, 0.0)
        pix = Pix(merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price)
        pix.set_description(f"Pagamento Plano {plan.capitalize()}")
        pix_code = pix.get_br_code_static(pix_key=PIX_PAYLOAD_STRING) # Usar a chave estática
        send_whatsapp_message(phone, f"Ótimo! Para o plano *{plan.replace('_', ' ').capitalize()}* (R$ {price:.2f}), pague com o PIX abaixo:")
        send_whatsapp_message(phone, pix_code)
        send_whatsapp_message(phone, "Depois de pagar, é só me enviar a *foto do comprovante* que eu libero seus arquivos! ✨")
        update_user(phone, {'state': 'awaiting_payment_proof'})
        return
    try:
        choice = int(message)
        if 1 <= choice <= len(CONVERSATION_FLOW):
            key_to_edit, _ = CONVERSATION_FLOW[choice-1]
            update_user(phone, {'state': f'editing_{key_to_edit}'})
            send_whatsapp_message(phone, f"Ok, vamos corrigir *{key_to_edit.replace('_', ' ')}*. Envie a informação correta.")
        else: raise ValueError()
    except (ValueError, IndexError):
        send_whatsapp_message(phone, "Não entendi. Digite o *número* do item ou *'finalizar'*.")

def create_editing_handler(edit_step_index):
    key_to_edit, _ = CONVERSATION_FLOW[edit_step_index]
    @handle_state(f'editing_{key_to_edit}')
    def editing_handler(user, message_data):
        phone, message = user['phone'], message_data.get('text', '')
        resume_data = json.loads(user['resume_data'])
        extracted_info = extract_info_from_message(f"Qual o novo valor para {key_to_edit}?", message)
        resume_data[key_to_edit] = extracted_info
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        send_whatsapp_message(phone, "Corrigido! 👍")
        show_review_menu(phone, resume_data)
for i in range(len(CONVERSATION_FLOW)): create_editing_handler(i)

@handle_state('awaiting_payment_proof')
def handle_payment_proof(user, message_data):
    phone = user['phone']
    if 'image' in message_data:
        image_url = message_data['image']['url']
        send_whatsapp_message(phone, "Oba, recebi seu comprovante! 🕵️‍♂️ Analisando com a IA, só um segundo...")
        analysis = analyze_pix_receipt(image_url)
        if analysis.get('verified'):
            send_whatsapp_message(phone, f"Pagamento confirmado! ✅\nMotivo: {analysis.get('reason')}")
            send_whatsapp_message(phone, "Estou preparando seus arquivos...")
            update_user(phone, {'payment_verified': 1})
            deliver_final_product(get_user(phone))
        else:
            send_whatsapp_message(phone, f"Hmm, não confirmei seu pagamento. 😕\nMotivo: {analysis.get('reason')}\nTente enviar uma imagem mais nítida.")
    else:
        send_whatsapp_message(phone, "Ainda não recebi a imagem. É só me enviar a foto do comprovante.")

def deliver_final_product(user):
    phone, plan, template = user['phone'], user['plan'], user['template']
    resume_data = json.loads(user['resume_data'])
    pdf_path = generate_resume_pdf(resume_data, template)
    send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo')}.pdf", "Seu currículo novinho em folha!")
    os.remove(pdf_path)
    if plan in ['premium', 'revisao_humana']:
        send_whatsapp_message(phone, "Gerando seus bônus premium...")
        send_whatsapp_message(phone, "[Arquivo Simulado] Curriculo_em_Ingles.pdf")
        send_whatsapp_message(phone, "[Arquivo Simulado] Carta_de_Apresentacao.pdf")
    if plan == 'revisao_humana':
        send_whatsapp_message(phone, "Sua revisão foi enviada para nossa equipe! Em até 24h úteis um especialista entrará em contato. 👨‍💼")
    send_whatsapp_message(phone, f"Prontinho! Obrigado por usar o {BOT_NAME}. Sucesso! 🚀")
    update_user(phone, {'state': 'completed'})

@handle_state('completed')
def handle_completed(user, message_data):
    send_whatsapp_message(user['phone'], "Olá! Vi que já completou seu currículo. Se precisar de algo mais, é só chamar!")

def handle_default(user, message_data):
    send_whatsapp_message(user['phone'], "Desculpe, não entendi. Para recomeçar, digite 'oi'.")

# ==============================================================================
# --- WEBHOOK (PONTO DE ENTRADA DAS MENSAGENS)
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"Webhook recebido: {json.dumps(data, indent=2)}")
        phone = data.get('phone')
        message_data = {}
        if data.get('text'):
            message_data['text'] = data.get('text', {}).get('message', '')
        elif data.get('image') and 'imageUrl' in data.get('image', {}):
            message_data['image'] = {'url': data['image']['imageUrl']}
        if phone and message_data:
            process_message(phone, message_data)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logging.error(f"Erro crítico no webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==============================================================================
# --- TAREFAS AGENDADAS (LEMBRETES)
# ==============================================================================
def check_abandoned_sessions():
    with app.app_context():
        logging.info("Verificando sessões abandonadas...")
        conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        time_limit = datetime.now() - timedelta(hours=24)
        cursor.execute("SELECT * FROM users WHERE last_interaction < ? AND state NOT IN ('completed', 'reminded')", (time_limit,))
        abandoned_users = cursor.fetchall()
        for user in abandoned_users:
            logging.info(f"Enviando lembrete para: {user['phone']}")
            message = f"Olá, {BOT_NAME} passando para dar um oi! 👋 Vi que começamos a montar seu currículo mas não terminamos. Que tal continuarmos de onde paramos?"
            send_whatsapp_message(user['phone'], message)
            update_user(user['phone'], {'state': 'reminded'})
        conn.close()

# ==============================================================================
# --- INICIALIZAÇÃO DO SERVIDOR E BANCO DE DADOS PARA DEPLOY
# ==============================================================================
init_database()
if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_abandoned_sessions, 'interval', hours=6)
    scheduler.start()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
