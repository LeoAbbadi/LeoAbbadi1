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
import openai # Apenas a OpenAI é necessária agora
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
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Configuração da IA da OpenAI (GPT) - PARA TEXTO E IMAGENS
try:
    openai.api_key = OPENAI_API_KEY
    if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"):
        raise ValueError("Chave da OpenAI inválida ou não configurada.")
    logging.info("API da OpenAI configurada com sucesso.")
except Exception as e:
    logging.error(f"Falha ao configurar a API da OpenAI: {e}")

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
# --- FUNÇÕES DE INTELIGÊNCIA ARTIFICIAL (100% OPENAI)
# ==============================================================================
def get_openai_response(prompt_messages, is_json=False):
    if not openai.api_key: return "Desculpe, minha IA (OpenAI) não está configurada."
    try:
        model_to_use = "gpt-4o" 
        
        # Habilita o modo JSON se solicitado
        response_format = {"type": "json_object"} if is_json else {"type": "text"}

        completion = openai.chat.completions.create(
            model=model_to_use,
            messages=prompt_messages,
            temperature=0.7,
            response_format=response_format
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Erro na API da OpenAI: {e}")
        return "Tive um problema para processar sua resposta. Vamos tentar de novo."

def extract_info_from_message(question, user_message):
    system_prompt = "Você é um assistente que extrai informações de uma conversa. Extraia APENAS a informação principal da resposta do usuário, sem a fraseologia extra. Por exemplo, se a pergunta é 'Qual seu nome completo?' e a resposta é 'o meu nome completo é joão da silva', extraia apenas 'joão da silva'. Se a resposta for 'não quero informar', extraia 'Não informado'."
    user_prompt = f'Pergunta feita: "{question}"\nResposta do usuário: "{user_message}"\n\nInformação extraída:'
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    return get_openai_response(messages)

def analyze_pix_receipt(image_url):
    system_prompt = f'Analise a imagem de um comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}" e a instituição de destino é "Mercado Pago" ou "MercadoPago". Responda APENAS com um objeto JSON com as chaves "verified" (true/false) e "reason" (uma breve explicação em português). Não inclua a formatação markdown ```json``` na resposta.'
    
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": system_prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    }]
    
    try:
        json_response_str = get_openai_response(messages, is_json=True)
        return json.loads(json_response_str)
    except Exception as e:
        logging.error(f"Erro ao analisar comprovante PIX com OpenAI: {e}", exc_info=True)
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
        if content and content != '[]' and content.lower() != 'pular' and content.lower() != 'não informado':
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
    ('resumo', 'Vamos caprichar! Escreva um pequeno resumo sobre você e seus objetivos. (Se não tiver, é só dizer "pular").'),
    ('experiencias', 'Agora, me conte sobre suas experiências profissionais. Pode enviar uma de cada vez e, quando terminar, digite "pronto".'),
    ('formacao', 'Qual a sua formação? (Ex: Ensino Médio Completo, Graduação em Administração)'),
    ('habilidades', 'Quais são suas principais habilidades? (Ex: Comunicação, Pacote Office). Pode listar várias, separando por vírgula.'),
    ('cursos', 'Você tem algum curso ou certificação? Se sim, me conte um por um. Quando acabar, é só dizer "pronto".')
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
    send_whatsapp_message(phone, f"Olá! Eu sou o {BOT_NAME} 🤖, seu novo assistente de carreira. Vou te ajudar a criar um currículo profissional incrível!")
    show_payment_options(phone)

def show_payment_options(phone):
    message = f"Para começarmos, conheça nossos planos:\n\n📄 *PLANO BÁSICO - R$ {PRECO_BASICO:.2f}*\n- Currículo em PDF em um dos nossos 5 templates.\n\n✨ *PLANO PREMIUM - R$ {PRECO_PREMIUM:.2f}*\n- Tudo do Básico, e mais:\n- Versão do currículo em Inglês.\n- Carta de apresentação profissional.\n\n👨‍💼 *REVISÃO HUMANA - R$ {PRECO_REVISAO_HUMANA:.2f}*\n- Tudo do Premium, e mais:\n- Revisão de um especialista de RH.\n\nDigite *básico*, *premium* ou *revisão* para escolher seu plano e começarmos a criar!"
    send_whatsapp_message(phone, message)
    update_user(phone, {'state': 'awaiting_plan_choice'})

@handle_state('awaiting_plan_choice')
def handle_plan_choice(user, message_data):
    phone = user['phone']
    choice = message_data.get('text', '').lower().strip().replace('á', 'a')
    plans = {'basico': 'basico', 'premium': 'premium', 'revisao': 'revisao_humana', 'revisão': 'revisao_humana'}
    if choice in plans:
        plan_name = plans[choice]
        update_user(phone, {'plan': plan_name})
        template_message = "Ótima escolha! Agora, vamos escolher o visual do seu currículo. Qual destes 5 estilos você prefere?\n\n1. *Clássico*\n2. *Moderno*\n3. *Criativo*\n4. *Minimalista*\n5. *Técnico*\n\nÉ só me dizer o número ou o nome."
        send_whatsapp_message(phone, template_message)
        update_user(phone, {'state': 'choosing_template'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Por favor, escolha entre *básico*, *premium* ou *revisão*.")

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone = user['phone']
    message = message_data.get('text', '').lower().strip()
    template_map = {'1': 'classico', 'clássico': 'classico', 'classico': 'classico',
                    '2': 'moderno', 'moderno': 'moderno',
                    '3': 'criativo', 'criativo': 'criativo',
                    '4': 'minimalista', 'minimalista': 'minimalista',
                    '5': 'tecnico', 'técnico': 'tecnico', 'tecnico': 'tecnico'}
    chosen_template = template_map.get(message)
    if chosen_template:
        update_user(phone, {'template': chosen_template, 'state': 'flow_nome_completo'})
        send_whatsapp_message(phone, f"Perfeito! Vamos criar seu currículo no estilo *{chosen_template.capitalize()}*.")
        send_whatsapp_message(phone, CONVERSATION_FLOW[0][1])
    else:
        send_whatsapp_message(phone, "Não entendi sua escolha. Por favor, me diga o nome ou o número do template (1 a 5).")

def create_flow_handler(current_step_index):
    current_key, current_question = CONVERSATION_FLOW[current_step_index]
    @handle_state(f'flow_{current_key}')
    def flow_handler(user, message_data):
        phone, message = user['phone'], message_data.get('text', '')
        resume_data = json.loads(user['resume_data'])
        is_list_field = current_key in ['experiencias', 'cursos']
        
        simple_command = message.lower().strip()
        if is_list_field and simple_command in ['pronto', 'ok', 'finalizar']:
            go_to_next_step(phone, resume_data, current_step_index)
            return
        
        if current_key == 'resumo' and simple_command == 'pular':
            extracted_info = "Não informado"
        else:
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
                next_question = next_question.format(nome=user_name.capitalize())
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
        plan = user['plan']
        prices = {'basico': PRECO_BASICO, 'premium': PRECO_PREMIUM, 'revisao_humana': PRECO_REVISAO_HUMANA}
        price = prices.get(plan, 0.0)
        pix_code = PIX_PAYLOAD_STRING 
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
            send_whatsapp_message(phone, f"Ok, vamos corrigir *{key_to_edit.replace('_', ' ')}*. Por favor, envie a informação correta.")
        else: raise ValueError()
    except (ValueError, IndexError):
        send_whatsapp_message(phone, "Não entendi. Por favor, digite o *número* do item ou *'finalizar'*.")

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

@handle_state('awaiting_payment
