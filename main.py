# -*- coding: utf-8 -*-
# VERSÃO COM TEMPLATE DE PDF AVANÇADO E PROFISSIONAL (SEM FOTO)

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
import openai
from flask import Flask, request, jsonify
from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler

# Configuração do logging
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

# Configuração da IA da OpenAI
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

# --- FONTES PARA PDF ---
FONT_DIR = os.path.join(DATA_DIR, 'fonts')
if not os.path.exists(FONT_DIR):
    os.makedirs(FONT_DIR)

def download_font(url, dest_path):
    if not os.path.exists(dest_path):
        logging.info(f"Baixando fonte de {url}...")
        try:
            r = requests.get(url, allow_redirects=True)
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                f.write(r.content)
            logging.info(f"Fonte salva em {dest_path}")
        except Exception as e:
            logging.error(f"Falha ao baixar fonte: {e}")

def setup_fonts():
    dejavu_sans_url = "https://github.com/dejavufonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
    dejavu_sans_bold_url = "https://github.com/dejavufonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf"
    download_font(dejavu_sans_url, os.path.join(FONT_DIR, "DejaVuSans.ttf"))
    download_font(dejavu_sans_bold_url, os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))

# ==============================================================================
# --- BANCO DE DADOS
# ==============================================================================
def init_database():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY, state TEXT, resume_data TEXT,
            plan TEXT DEFAULT 'none', template TEXT DEFAULT 'none',
            payment_verified INTEGER DEFAULT 0, last_interaction TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Banco de dados inicializado.")

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
# --- COMUNICAÇÃO WHATSAPP
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
# --- FUNÇÕES DE IA (OPENAI)
# ==============================================================================
def get_openai_response(prompt_messages, is_json=False):
    if not openai.api_key: return "Desculpe, minha IA (OpenAI) não está configurada."
    try:
        model_to_use = "gpt-4o"
        response_format = {"type": "json_object"} if is_json else {"type": "text"}
        completion = openai.chat.completions.create(
            model=model_to_use, messages=prompt_messages,
            temperature=0.7, response_format=response_format
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Erro na API da OpenAI: {e}")
        return "Tive um problema para processar sua resposta. Vamos tentar de novo."

def extract_info_from_message(question, user_message):
    system_prompt = "Você é um assistente que extrai a informação principal da resposta de um usuário, sem frases extras. Ex: se a pergunta é 'Qual seu nome?' e a resposta é 'meu nome é joão da silva', extraia 'joão da silva'. Se a resposta for 'não quero informar', extraia 'Não informado'."
    user_prompt = f'Pergunta: "{question}"\nResposta: "{user_message}"\n\nInformação extraída:'
    return get_openai_response([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])

def analyze_pix_receipt(image_url):
    system_prompt = f'Analise a imagem de um comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}" e a instituição é "Mercado Pago" ou "MercadoPago". Responda APENAS com um objeto JSON com as chaves "verified" (true/false) e "reason" (uma breve explicação em português). Não inclua markdown ```json```.'
    messages = [{"role": "user", "content": [{"type": "text", "text": system_prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
    try:
        json_response_str = get_openai_response(messages, is_json=True)
        return json.loads(json_response_str)
    except Exception as e:
        logging.error(f"Erro ao analisar comprovante PIX com OpenAI: {e}", exc_info=True)
        return {'verified': False, 'reason': 'Não consegui ler a imagem do comprovante.'}

def translate_resume_data_to_english(resume_data):
    system_prompt = "Você é um tradutor especialista em currículos. Traduza o seguinte JSON de dados de um currículo do português para o inglês profissional. Mantenha a mesma estrutura JSON, mas traduza tanto as chaves (keys) quanto os valores (values) para o inglês. Use chaves em inglês como: 'full_name', 'city_state', 'phone', 'email', 'desired_role', 'professional_summary', 'work_experience', 'education', 'skills', 'courses_certifications'."
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(resume_data, ensure_ascii=False)}]
    translated_json_str = get_openai_response(messages, is_json=True)
    try:
        return json.loads(translated_json_str)
    except json.JSONDecodeError:
        return None

def generate_cover_letter_text(resume_data):
    system_prompt = "Você é um coach de carreira e especialista em RH. Escreva uma carta de apresentação profissional, na primeira pessoa (como se fosse o candidato), usando os dados do currículo a seguir. A carta deve ser concisa, direta e impactante. Comece com uma saudação profissional, apresente o candidato e seu objetivo. No corpo, destaque 1 ou 2 pontos fortes da experiência ou habilidades que se conectem com o cargo desejado. Encerre com uma chamada para ação, convidando para uma conversa e agradecendo a oportunidade. Não use clichês."
    user_prompt = f"Dados do currículo para basear a carta:\n{json.dumps(resume_data, indent=2, ensure_ascii=False)}\n\nEscreva a carta de apresentação:"
    return get_openai_response([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])

def improve_experience_descriptions(experiences):
    system_prompt = "Você é um especialista em RH que otimiza currículos. Reescreva a lista de experiências profissionais a seguir para que foquem em resultados e ações, usando verbos de impacto. Transforme responsabilidades em conquistas. Retorne uma lista JSON de strings."
    user_prompt = f"Experiências originais: {json.dumps(experiences, ensure_ascii=False)}\n\nReescreva-as de forma profissional e focada em resultados (retorne apenas a lista em JSON):"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    response_str = get_openai_response(messages, is_json=True)
    try:
        response_data = json.loads(response_str)
        if isinstance(response_data, dict):
            for key in response_data:
                if isinstance(response_data[key], list): return response_data[key]
        elif isinstance(response_data, list): return response_data
        return experiences
    except:
        return experiences

# ==============================================================================
# --- GERAÇÃO DE PDF
# ==============================================================================
def generate_resume_pdf(data, template_choice):
    templates = {
        'classico': generate_template_moderno, 'moderno': generate_template_moderno,
        'criativo': generate_template_moderno, 'minimalista': generate_template_moderno,
        'tecnico': generate_template_moderno
    }
    pdf_function = templates.get(template_choice, generate_template_moderno)
    path = os.path.join(TEMP_DIR, f"curriculo_{data.get('phone', 'user')}.pdf")
    pdf_function(data, path)
    return path

def generate_simple_text_pdf(text, path):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font('DejaVu', '', os.path.join(FONT_DIR, 'DejaVuSans.ttf'), uni=True)
        pdf.set_font('DejaVu', '', 11)
    except RuntimeError:
        logging.warning("Fonte DejaVu não encontrada, usando Helvetica.")
        pdf.set_font("Helvetica", '', 11)
    pdf.multi_cell(0, 7, text)
    pdf.output(path)

def generate_template_moderno(data, path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    try:
        pdf.add_font('DejaVu', '', os.path.join(FONT_DIR, 'DejaVuSans.ttf'), uni=True)
        pdf.add_font('DejaVu', 'B', os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'), uni=True)
        FONT_REGULAR, FONT_BOLD = 'DejaVu', 'DejaVu'
    except RuntimeError:
        FONT_REGULAR, FONT_BOLD = 'Helvetica', 'Helvetica'
    
    SIDEBAR_COLOR = (52, 58, 64)
    ACCENT_COLOR = (73, 126, 174)
    
    # Coluna Esquerda (Sidebar)
    pdf.set_fill_color(*SIDEBAR_COLOR)
    pdf.rect(0, 0, 70, 297, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 20)
    
    # Contato
    pdf.set_font(FONT_BOLD, 'B', 12)
    pdf.cell(0, 10, "CONTATO" if 'cidade_estado' in data else 'CONTACT', 0, 1)
    pdf.set_font(FONT_REGULAR, '', 9)
    
    def add_contact_info(icon_url, text):
        if text:
            y_before = pdf.get_y()
            try:
                # O fpdf2 pode carregar imagens de URLs diretamente
                pdf.image(icon_url, x=10, y=y_before + 1, w=4, h=4)
            except Exception as e:
                logging.warning(f"Não foi possível carregar o ícone: {e}")
            pdf.set_xy(16, y_before)
            pdf.multi_cell(50, 5, text, 0, 'L')
            pdf.ln(2)

    add_contact_info("https://i.imgur.com/3O5MUNR.png", data.get('email'))
    add_contact_info("https://i.imgur.com/d2owq8a.png", data.get('telefone') or data.get('phone'))
    add_contact_info("https://i.imgur.com/sU9yB6j.png", data.get('cidade_estado') or data.get('city_state'))
    pdf.ln(8)
    
    # Função genérica para seções da sidebar
    def add_sidebar_section(title_pt, title_en, content_pt, content_en):
        title = title_en if content_en else title_pt
        content = content_en if content_en else content_pt
        if content:
            pdf.set_x(10)
            pdf.set_font(FONT_BOLD, 'B', 12)
            pdf.cell(0, 10, title.upper(), 0, 1)
            pdf.set_font(FONT_REGULAR, '', 9)
            pdf.multi_cell(55, 5, str(content).replace(",", "\n• "), 0, 'L')
            pdf.ln(8)
            
    add_sidebar_section("Formação", "Education", data.get('formacao'), data.get('education'))
    add_sidebar_section("Habilidades", "Skills", data.get('habilidades'), data.get('skills'))

    # Coluna da Direita
    pdf.set_xy(80, 15)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font(FONT_BOLD, 'B', 28)
    pdf.multi_cell(120, 12, data.get('nome_completo') or data.get('full_name'))
    pdf.set_font(FONT_REGULAR, '', 14)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(80)
    pdf.cell(0, 8, data.get('cargo') or data.get('desired_role'), 0, 1, 'L')
    pdf.ln(10)
    
    def add_right_section(title, content):
        if content and str(content) != '[]' and 'pular' not in str(content).lower() and 'não informado' not in str(content).lower():
            pdf.set_x(80)
            pdf.set_font(FONT_BOLD, 'B', 14)
            pdf.set_text_color(0,0,0)
            pdf.cell(0, 8, title.upper(), 0, 1, 'L')
            pdf.set_draw_color(*ACCENT_COLOR)
            pdf.line(80, pdf.get_y(), 130, pdf.get_y())
            pdf.ln(5)
            pdf.set_font(FONT_REGULAR, '', 10)
            cleaned_content = str(content).replace("['", "\n• ").replace("']", "").replace("', '", "\n• ").replace("[]", "")
            pdf.multi_cell(120, 6, cleaned_content)
            pdf.ln(6)

    # Mapeia títulos para garantir o idioma correto
    add_right_section(data.get('resumo', 'Resumo Profissional'), data.get('resumo') or data.get('professional_summary'))
    add_right_section(data.get('experiencias', 'Experiência Profissional'), data.get('experiencias') or data.get('work_experience'))
    add_right_section(data.get('cursos', 'Cursos e Certificações'), data.get('cursos') or data.get('courses_certifications'))
    pdf.output(path)

# ==============================================================================
# --- FLUXO DA CONVERSA
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
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    if 'básico' in choice or 'basico' in choice: plan_name = 'basico'
    elif 'premium' in choice: plan_name = 'premium'
    elif 'revisão' in choice or 'revisao' in choice or 'humana' in choice: plan_name = 'revisao_humana'
    else: plan_name = None
    if plan_name:
        update_user(phone, {'plan': plan_name})
        template_message = "Ótima escolha! Agora, vamos escolher o visual do seu currículo:\n\n1. *Moderno (Recomendado)*\n2. *Clássico*\n3. *Criativo*\n4. *Minimalista*\n5. *Técnico*\n\nÉ só me dizer o número ou o nome."
        send_whatsapp_message(phone, template_message)
        update_user(phone, {'state': 'choosing_template'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Escolha *básico*, *premium* ou *revisão*.")

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone, message = user['phone'], message_data.get('text', '').lower().strip()
    template_map = {'1': 'moderno', 'moderno': 'moderno', '2': 'classico', 'clássico': 'classico', '3': 'criativo', '4': 'minimalista', '5': 'tecnico'}
    chosen_template = template_map.get(message, message)
    if chosen_template in template_map.values():
        update_user(phone, {'template': chosen_template, 'state': 'flow_nome_completo'})
        send_whatsapp_message(phone, f"Perfeito! Vamos criar seu currículo no estilo *{chosen_template.capitalize()}*.")
        send_whatsapp_message(phone, CONVERSATION_FLOW[0][1])
    else:
        send_whatsapp_message(phone, "Não entendi. Diga o nome ou o número do template.")

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
        if current_key == 'resumo' and simple_command == 'pular': extracted_info = "Não informado"
        else: extracted_info = extract_info_from_message(current_question, message)
        if is_list_field:
            if current_key not in resume_data: resume_data[current_key] = []
            resume_data[current_key].append(extracted_info)
            send_whatsapp_message(phone, "Legal, adicionei! Pode me mandar o próximo ou digite *'pronto'*.")
        else:
            resume_data[current_key] = extracted_info
            go_to_next_step(phone, resume_data, current_step_index)
        update_user(phone, {'resume_data': json.dumps(resume_data)})
    def go_to_next_step(phone, resume_data, current_idx):
        if CONVERSATION_FLOW[current_idx][0] == 'experiencias' and resume_data.get('experiencias'):
            update_user(phone, {'state': 'awaiting_improve_choice'})
            send_whatsapp_message(phone, "Ótimo. Percebi que você adicionou suas experiências. Gostaria que eu usasse minha IA para reescrevê-las de uma forma mais profissional e focada em resultados? (Responda com *sim* ou *não*)")
            return
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

@handle_state('awaiting_improve_choice')
def handle_improve_choice(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    resume_data = json.loads(user['resume_data'])
    if choice == 'sim':
        send_whatsapp_message(phone, "Excelente! Deixa comigo, estou otimizando seus textos... ✍️")
        improved_experiences = improve_experience_descriptions(resume_data.get('experiencias', []))
        resume_data['experiencias'] = improved_experiences
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        send_whatsapp_message(phone, "Prontinho! Textos melhorados.")
    else:
        send_whatsapp_message(phone, "Sem problemas! Vamos continuar.")
    current_key_index = [k for k, q in CONVERSATION_FLOW].index('experiencias')
    next_key, next_question = CONVERSATION_FLOW[current_key_index + 1]
    send_whatsapp_message(phone, next_question)
    update_user(phone, {'state': f'flow_{next_key}'})

def show_review_menu(phone, resume_data):
    review_text = "Antes de finalizar, revise seus dados. Para corrigir, diga o número do item:\n\n"
    for i, (key, _) in enumerate(CONVERSATION_FLOW):
        review_text += f"*{i+1}. {key.replace('_', ' ').capitalize()}:* {resume_data.get(key, 'Não preenchido')}\n"
    review_text += "\nSe estiver tudo certo, digite *'finalizar'* para ir ao pagamento!"
    send_whatsapp_message(phone, review_text)
    update_user(phone, {'state': 'awaiting_review_choice'})

@handle_state('awaiting_review_choice')
def handle_review_choice(user, message_data):
    phone, message = user['phone'], message_data.get('text', '').lower().strip()
    if message in ['finalizar', 'pagar', 'tudo certo', 'ok']:
        plan, prices = user['plan'], {'basico': PRECO_BASICO, 'premium': PRECO_PREMIUM, 'revisao_humana': PRECO_REVISAO_HUMANA}
        price = prices.get(plan, 0.0)
        send_whatsapp_message(phone, f"Ótimo! Para o plano *{plan.replace('_', ' ').capitalize()}* (R$ {price:.2f}), pague com o PIX abaixo:")
        send_whatsapp_message(phone, PIX_PAYLOAD_STRING)
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
            send_whatsapp_message(phone, "Pagamento confirmado! ✅")
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
    send_whatsapp_message(phone, "Preparando seu currículo principal...")
    pdf_path = generate_resume_pdf(resume_data, template)
    send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo', 'user').split(' ')[0]}.pdf", "Seu currículo novinho em folha!")
    os.remove(pdf_path)
    if plan in ['premium', 'revisao_humana']:
        send_whatsapp_message(phone, "Agora, gerando seus bônus do plano premium...")
        send_whatsapp_message(phone, "Traduzindo seu currículo para o Inglês...")
        english_data = translate_resume_data_to_english(resume_data)
        if english_data:
            english_pdf_path = generate_resume_pdf(english_data, template)
            send_whatsapp_document(phone, english_pdf_path, f"Resume_English_{english_data.get('full_name', 'user').split(' ')[0]}.pdf", "Aqui está sua versão em Inglês!")
            os.remove(english_pdf_path)
        send_whatsapp_message(phone, "Escrevendo sua carta de apresentação personalizada...")
        cover_letter_text = generate_cover_letter_text(resume_data)
        if cover_letter_text:
            letter_path = os.path.join(TEMP_DIR, f"carta_apresentacao_{phone}.pdf")
            generate_simple_text_pdf(cover_letter_text, letter_path)
            send_whatsapp_document(phone, letter_path, "Carta_de_Apresentacao.pdf", "E aqui sua carta de apresentação!")
            os.remove(letter_path)
    if plan == 'revisao_humana':
        send_whatsapp_message(phone, "Sua solicitação de revisão foi enviada para nossa equipe! Em até 24h úteis um especialista entrará em contato. 👨‍💼")
    send_whatsapp_message(phone, f"Prontinho! Muito obrigado por usar o {BOT_NAME}. Sucesso! 🚀")
    update_user(phone, {'state': 'completed'})

@handle_state('completed')
def handle_completed(user, message_data):
    send_whatsapp_message(user['phone'], "Olá! Vi que você já completou seu currículo. Se precisar de algo mais, é só chamar!")

def handle_default(user, message_data):
    send_whatsapp_message(user['phone'], "Desculpe, não entendi o que você quis dizer. Para recomeçar, digite 'oi'.")

# ==============================================================================
# --- WEBHOOK
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"Webhook recebido: {json.dumps(data, indent=2)}")
        phone = data.get('phone')
        message_data = {}
        if data.get('text') and data.get('text', {}).get('message'):
            message_data['text'] = data['text']['message']
        elif data.get('image') and data.get('image', {}).get('imageUrl'):
            message_data['image'] = {'url': data['image']['imageUrl']}
        if phone and message_data:
            process_message(phone, message_data)
        else:
            logging.warning(f"Webhook de {phone} recebido sem dados de mensagem válidos.")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logging.error(f"Erro crítico no webhook: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==============================================================================
# --- TAREFAS AGENDADAS
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
# --- INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================
setup_fonts()
init_database()
if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_abandoned_sessions, 'interval', hours=6)
    scheduler.start()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
