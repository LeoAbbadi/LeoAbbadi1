# -*- coding: utf-8 -*-
# VERSÃO FINAL - NÍVEL OSCAR (09/07/2025) - FORMATAÇÃO, IA E TEMPLATES APRIMORADOS

# ==============================================================================
# --- 1. IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
# ==============================================================================
import os
import sqlite3
import json
import base64
import logging
import threading
from datetime import datetime, timedelta
import requests
import openai
from flask import Flask, request, jsonify
from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# --- 2. INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- NÚMEROS E COMANDOS ---
ADMIN_PHONE_NUMBER = "5551994914188"
PULAR_COMMANDS = ['pular', 'nao', 'não', 'n', 'ignorar', 'não tenho']
PRONTO_COMMANDS = ['pronto', 'acabei', 'fim', 'só isso', 'finalizar']
REINICIAR_COMMANDS = ['oi', 'ola', 'olá', 'recomeçar', 'começar', 'menu', 'inicio']

# --- CHAVES E CONFIGS ---
ZAPI_INSTANCE_ID = os.environ.get('ZAPI_INSTANCE_ID')
ZAPI_TOKEN = os.environ.get('ZAPI_TOKEN')
ZAPI_CLIENT_TOKEN = os.environ.get('ZAPI_CLIENT_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

try:
    openai.api_key = OPENAI_API_KEY
    if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"): raise ValueError("Chave da OpenAI inválida.")
    logging.info("API da OpenAI configurada com sucesso.")
except Exception as e:
    logging.error(f"Falha ao configurar a API da OpenAI: {e}")

# --- CONFIGS DE PAGAMENTO E PLANOS ---
PIX_RECIPIENT_NAME = "Leonardo Maciel Abbadi"
PIX_PAYLOAD_STRING = "00020126580014br.gov.bcb.pix0136fd3412eb-9577-41ea-ba4d-12293570c0155204000053039865802BR5922Leonardo Maciel Abbadi6008Brasilia62240520daqr1894289448628220630439D1"
PRECO_BASICO, PRECO_PREMIUM, PRECO_REVISAO_HUMANA, PRECO_ASSINATURA = 7.99, 13.99, 16.99, 19.90
CREDITOS_BASICO, CREDITOS_PREMIUM, CREDITOS_ASSINATURA = 3, 5, 99

# --- CAMINHOS DE ARQUIVOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('RENDER_DISK_PATH', SCRIPT_DIR)
DATABASE_FILE = os.path.join(DATA_DIR, 'cadu_database.db')
FONT_DIR = os.path.join(SCRIPT_DIR, 'fonts')
TEMP_DIR = "/tmp"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# ==============================================================================
# --- 3. FUNÇÕES DE BANCO DE DADOS
# ==============================================================================
def init_database():
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY, state TEXT, resume_data TEXT,
            plan TEXT DEFAULT 'none', template TEXT DEFAULT 'none',
            payment_verified INTEGER DEFAULT 0, last_interaction TIMESTAMP,
            current_experience TEXT, payment_timestamp TIMESTAMP,
            credits INTEGER DEFAULT 0, subscription_valid_until TIMESTAMP,
            editing_field TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Banco de dados inicializado com novo schema.")

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
            'phone': phone, 'state': 'awaiting_welcome', 'resume_data': json.dumps({'cargo': ''}),
            'plan': 'none', 'template': 'none', 'payment_verified': 0,
            'last_interaction': datetime.now(), 'current_experience': json.dumps({}),
            'payment_timestamp': None, 'credits': 0, 'subscription_valid_until': None,
            'editing_field': None
        }
        initial_data.update(data)
        columns = ', '.join(initial_data.keys())
        placeholders = ', '.join('?' * len(initial_data))
        sql = f'INSERT INTO users ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, tuple(initial_data.values()))
    else:
        data['last_interaction'] = datetime.now()
        set_clause = ', '.join([f'{key} = ?' for key in data.keys()])
        values = list(data.values()) + [phone]
        sql = f"UPDATE users SET {set_clause} WHERE phone = ?"
        cursor.execute(sql, tuple(values))
    conn.commit()
    conn.close()

# ==============================================================================
# --- 4. COMUNICAÇÃO E PROCESSAMENTO ASSÍNCRONO
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
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename, "caption": caption}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao enviar documento para {phone}: {e}")

def run_long_task_in_background(target_func, args=()):
    logging.info(f"Iniciando tarefa {target_func.__name__} em segundo plano.")
    thread = threading.Thread(target=target_func, args=args)
    thread.daemon = True
    thread.start()

# ==============================================================================
# --- 5. FUNÇÕES DE IA E FORMATAÇÃO (VERSÃO OSCAR)
# ==============================================================================
def get_openai_response(prompt_messages, is_json=False):
    if not openai.api_key: return None
    try:
        model_to_use = "gpt-4o"
        response_format = {"type": "json_object"} if is_json else {"type": "text"}
        completion = openai.chat.completions.create(model=model_to_use, messages=prompt_messages, temperature=0.3, response_format=response_format)
        response_content = completion.choices[0].message.content.strip()
        if is_json:
            try: json.loads(response_content)
            except json.JSONDecodeError:
                logging.error(f"OpenAI retornou JSON inválido: {response_content}")
                return None
        return response_content
    except Exception as e:
        logging.error(f"Erro na API da OpenAI: {e}")
        return None

def format_text(field_key, text):
    """Aplica formatação padronizada para diferentes tipos de campos."""
    if not isinstance(text, str): return text
    text = text.strip()
    if field_key in ['nome_completo', 'empresa', 'cargo', 'formacao', 'cidade_estado']:
        # O próprio prompt da IA já cuidará da capitalização inteligente
        return text
    elif field_key == 'email':
        return text.lower()
    elif field_key in ['resumo', 'descricao'] and text:
        # A IA também cuidará da gramática, então apenas retornamos
        return text
    return text

def extract_and_format_info(field_key, question, user_message):
    """Usa IA para extrair informação de forma inteligente e depois a formata."""
    system_prompt = "Você é um assistente que extrai a informação principal da resposta de um usuário, de forma limpa e direta, sem saudações ou frases adicionais. Apenas a informação pura."
    user_prompt_template = 'Pergunta: "{question}"\nResposta do usuário: "{user_message}"\n\nExtraia a informação relevante:'

    if field_key == 'periodo':
        system_prompt = "Você é um assistente que extrai um período de tempo da resposta de um usuário. Formate a resposta como 'Mês de Ano - Mês de Ano' ou 'Ano - Ano'. Ignore palavras como 'fiquei de', 'trabalhei entre'. Exemplo: se o usuário diz 'fevereiro de 2023 até janeiro 2025', extraia 'Fevereiro de 2023 - Janeiro de 2025'."
    elif field_key == 'nome_completo':
        system_prompt = "Você é um assistente que extrai um nome completo de pessoa. Corrija a capitalização de forma inteligente (ex: 'joão da silva' -> 'João da Silva'). Preste atenção em conectivos como 'de' e 'da', mantendo-os em minúsculo. Retorne apenas o nome."
    elif field_key == 'resumo' or field_key == 'descricao':
        system_prompt = "Você é um assistente que analisa a resposta de um usuário. Mantenha o tom original, mas corrija erros de digitação e gramática de forma sutil para garantir profissionalismo. Retorne apenas o texto corrigido."
        
    user_prompt = user_prompt_template.format(question=question, user_message=user_message)
    
    extracted_info = get_openai_response([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]) or user_message

    return format_text(field_key, extracted_info)

def analyze_pix_receipt(image_url):
    system_prompt = f'Analise a imagem de um comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}". Responda APENAS com um objeto JSON com a chave "verified" (true/false). Não inclua a formatação markdown ```json```.'
    messages = [{"role": "user", "content": [{"type": "text", "text": system_prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
    json_response_str = get_openai_response(messages, is_json=True)
    if json_response_str: return json.loads(json_response_str)
    return {'verified': False}

def translate_resume_data_to_english(resume_data):
    system_prompt = "Você é um tradutor especialista em currículos. Traduza o seguinte JSON de dados de um currículo do português para o inglês profissional. Traduza tanto as chaves (keys) quanto os valores (values) para o inglês. Use estas chaves em inglês: 'full_name', 'city_state', 'phone', 'email', 'desired_role', 'professional_summary', 'work_experience', 'education', 'skills', 'courses_certifications'. O valor de 'work_experience' e 'courses_certifications' devem ser uma lista de dicionários, traduza o conteúdo dentro deles também."
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(resume_data, ensure_ascii=False)}]
    translated_json_str = get_openai_response(messages, is_json=True)
    if translated_json_str:
        try: return json.loads(translated_json_str)
        except json.JSONDecodeError: return None
    return None

def improve_experience_descriptions(experiences):
    system_prompt = "Você é um especialista em RH que otimiza currículos. Reescreva a lista de experiências profissionais a seguir para que foquem em resultados e ações, usando verbos de impacto e um tom profissional. Transforme responsabilidades em conquistas. Mantenha a estrutura de lista de dicionários do JSON original e retorne apenas o JSON."
    user_prompt = f"Experiências originais: {json.dumps(experiences, ensure_ascii=False)}\n\nReescreva as descrições de forma profissional e focada em resultados (retorne apenas a lista em JSON):"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    response_str = get_openai_response(messages, is_json=True)
    if response_str:
        try:
            response_data = json.loads(response_str)
            if isinstance(response_data, dict) and 'work_experience' in response_data: return response_data['work_experience']
            elif isinstance(response_data, list): return response_data
        except (json.JSONDecodeError, TypeError): return experiences
    return experiences

def generate_interview_questions(resume_data):
    system_prompt = "Você é um recrutador sênior preparando uma entrevista para a vaga de '{cargo}'. Com base no currículo do candidato, crie uma lista de 5 a 7 perguntas de entrevista perspicazes e relevantes, misturando perguntas comportamentais (STAR: Situação, Tarefa, Ação, Resultado) e técnicas baseadas nas experiências e habilidades listadas. Formate a resposta como um texto único, com cada pergunta numerada."
    user_prompt = f"Currículo do candidato:\n{json.dumps(resume_data, indent=2, ensure_ascii=False)}\n\nListe as perguntas para a entrevista:"
    return get_openai_response([{"role": "system", "content": system_prompt.format(cargo=resume_data.get('cargo', ''))}, {"role": "user", "content": user_prompt}])

# ==============================================================================
# --- 6. GERAÇÃO DE PDF (VERSÃO OSCAR)
# ==============================================================================
class PDF(FPDF):
    def add_font_setup(self):
        try:
            # Garante que a pasta de fontes exista
            if not os.path.exists(FONT_DIR):
                os.makedirs(FONT_DIR)
                logging.warning(f"Pasta de fontes não encontrada, criada em {FONT_DIR}.")
            # Fontes DejaVu são essenciais para suportar ícones e caracteres especiais
            font_paths = {
                'DejaVu': os.path.join(FONT_DIR, 'DejaVuSans.ttf'),
                'DejaVuB': os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'),
                'DejaVuI': os.path.join(FONT_DIR, 'DejaVuSans-Oblique.ttf'),
                'DejaVuBI': os.path.join(FONT_DIR, 'DejaVuSans-BoldOblique.ttf'),
            }
            for name, path in font_paths.items():
                if not os.path.isfile(path): raise RuntimeError(f"Arquivo de fonte não encontrado: {path}. Faça o download da família de fontes 'DejaVu' e coloque os arquivos na pasta 'fonts'.")
            
            self.add_font('DejaVu', '', font_paths['DejaVu'], uni=True)
            self.add_font('DejaVu', 'B', font_paths['DejaVuB'], uni=True)
            self.add_font('DejaVu', 'I', font_paths['DejaVuI'], uni=True)
            self.add_font('DejaVu', 'BI', font_paths['DejaVuBI'], uni=True)
            self.font_regular = 'DejaVu'
            self.font_bold = 'DejaVu'
        except Exception as e:
            logging.error(f"ERRO CRÍTICO DE FONTE: {e}. Usando 'Helvetica' como alternativa, mas pode haver problemas de codificação.")
            self.font_regular = 'Helvetica'
            self.font_bold = 'Helvetica'
        self.set_font(self.font_regular, '', 10)

def generate_resume_pdf(data, template_choice, path):
    templates = {'moderno': generate_template_moderno, 'classico': generate_template_classico, 'criativo': generate_template_criativo}
    pdf_function = templates.get(template_choice, generate_template_moderno)
    pdf_function(data, path)

def generate_template_moderno(data, path):
    pdf = PDF()
    pdf.add_font_setup(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=15)
    SIDEBAR_COLOR, ACCENT_COLOR = (45, 52, 54), (26, 188, 156)
    lang = 'en' if 'full_name' in data else 'pt'

    # --- Barra Lateral ---
    pdf.set_fill_color(*SIDEBAR_COLOR); pdf.rect(0, 0, 70, 297, 'F')
    pdf.set_xy(10, 20); pdf.set_text_color(255, 255, 255)
    
    def add_sidebar_section(title, content_list, icon=''):
        if not content_list: return
        pdf.set_x(10); pdf.set_font(pdf.font_bold, 'B', 11); pdf.cell(55, 10, f"{icon} {title.upper()}", 0, 1)
        pdf.set_font(pdf.font_regular, '', 9)
        for item in content_list:
            pdf.set_x(12); pdf.multi_cell(55, 5, f"• {item}", 0, 'L')
        pdf.ln(5)

    contact_list = [
        f"📍 {data.get('cidade_estado') or data.get('city_state', '')}",
        f"📞 {data.get('telefone') or data.get('phone', '')}",
        f"✉️ {data.get('email', '')}"
    ]
    add_sidebar_section("Contato" if lang == 'pt' else "Contact", [item for item in contact_list if item.split(' ')[-1]])
    add_sidebar_section("Formação" if lang == 'pt' else "Education", [data.get('formacao') or data.get('education')])
    add_sidebar_section("Habilidades" if lang == 'pt' else "Skills", data.get('habilidades') or data.get('skills'))
    add_sidebar_section("Cursos", data.get('cursos') or data.get('courses_certifications'))

    # --- Conteúdo Principal ---
    pdf.set_xy(80, 20); pdf.set_text_color(40, 40, 40)
    pdf.set_font(pdf.font_bold, 'B', 28); pdf.multi_cell(120, 11, data.get('nome_completo') or data.get('full_name'))
    pdf.set_font(pdf.font_regular, '', 14); pdf.set_text_color(108, 122, 137); pdf.set_x(80)
    pdf.cell(0, 8, data.get('cargo') or data.get('desired_role'), 0, 1, 'L'); pdf.ln(10)

    def add_right_section(title, content):
        if not content or (isinstance(content, str) and ( 'pular' in content.lower() or 'não informado' in content.lower())): return
        pdf.set_x(80); pdf.set_font(pdf.font_bold, 'B', 12); pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 8, title.upper(), 0, 1, 'L'); pdf.set_draw_color(*ACCENT_COLOR); pdf.line(80, pdf.get_y(), 130, pdf.get_y()); pdf.ln(5)
        pdf.set_font(pdf.font_regular, '', 10); pdf.set_text_color(80, 80, 80)
        
        if isinstance(content, list) and all(isinstance(i, dict) for i in content): # Experiências
            for item in content:
                pdf.set_x(80); pdf.set_font(pdf.font_bold, 'B', 10); pdf.multi_cell(120, 6, f"{item.get('cargo', '')} | {item.get('empresa', '')}", 0, 'L')
                pdf.set_font(pdf.font_regular, 'I', 9); pdf.set_x(80); pdf.multi_cell(120, 5, item.get('periodo', ''), 0, 'L')
                pdf.set_font(pdf.font_regular, '', 10); pdf.set_x(83)
                pdf.multi_cell(115, 5, f"• {item.get('descricao', '')}"); pdf.ln(4)
        else: # Resumo
            pdf.set_x(80); pdf.multi_cell(120, 6, content)
        pdf.ln(6)

    title_map_pt = {"resumo": "Resumo Profissional", "experiencias": "Experiência Profissional"}
    title_map_en = {"professional_summary": "Professional Summary", "work_experience": "Work Experience"}
    add_right_section(title_map_pt.get('resumo'), data.get('resumo') or data.get('professional_summary'))
    add_right_section(title_map_pt.get('experiencias'), data.get('experiencias') or data.get('work_experience'))
    pdf.output(path)

def generate_template_classico(data, path):
    pdf = PDF()
    pdf.add_font_setup(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=15)
    lang = 'en' if 'full_name' in data else 'pt'

    # --- Cabeçalho ---
    pdf.set_font(pdf.font_bold, 'B', 24); pdf.cell(0, 10, (data.get('nome_completo') or data.get('full_name', '')).upper(), 0, 1, 'C')
    pdf.set_font(pdf.font_regular, '', 11)
    contato = f"{data.get('cidade_estado', '')} | {data.get('telefone', '')} | {data.get('email', '')}"
    pdf.cell(0, 8, contato, 0, 1, 'C'); pdf.ln(2)
    pdf.set_font(pdf.font_bold, '', 12); pdf.cell(0, 8, data.get('cargo', '').upper(), 0, 1, 'C')
    pdf.ln(5); pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(7)

    def add_section(title, content):
        if not content or (isinstance(content, str) and ( 'pular' in content.lower() or 'não informado' in content.lower())): return
        pdf.set_font(pdf.font_bold, 'B', 12); pdf.cell(0, 8, title.upper(), 0, 1, 'L'); pdf.ln(2)
        pdf.set_font(pdf.font_regular, '', 10)
        
        if isinstance(content, list) and all(isinstance(i, dict) for i in content): # Experiências
            for item in content:
                pdf.set_font(pdf.font_bold, 'B', 10); pdf.cell(0, 6, f"{item.get('cargo', '')}, {item.get('empresa', '')}", 0, 1)
                pdf.set_font(pdf.font_regular, 'I', 9); pdf.multi_cell(0, 5, item.get('periodo', ''), 0, 'L')
                pdf.set_font(pdf.font_regular, '', 10); pdf.multi_cell(0, 5, f"  • {item.get('descricao', '')}"); pdf.ln(3)
        elif isinstance(content, list): # Habilidades, Cursos
             for item in content: pdf.multi_cell(0, 5, f"• {item}")
        else: # Resumo, Formação
            pdf.multi_cell(0, 6, content)
        pdf.ln(5)

    title_map_pt = {"resumo": "Resumo", "experiencias": "Experiência Profissional", "formacao": "Formação Acadêmica", "habilidades": "Habilidades", "cursos": "Cursos e Certificações"}
    title_map_en = {"professional_summary": "Summary", "work_experience": "Work Experience", "education": "Education", "skills": "Skills", "courses_certifications": "Courses & Certifications"}
    
    add_section(title_map_pt.get('resumo'), data.get('resumo') or data.get('professional_summary'))
    add_section(title_map_pt.get('experiencias'), data.get('experiencias') or data.get('work_experience'))
    add_section(title_map_pt.get('formacao'), [data.get('formacao') or data.get('education')])
    add_section(title_map_pt.get('habilidades'), data.get('habilidades') or data.get('skills'))
    add_section(title_map_pt.get('cursos'), data.get('cursos') or data.get('courses_certifications'))
    pdf.output(path)

def generate_template_criativo(data, path):
    pdf = PDF()
    pdf.add_font_setup(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=10)
    PRIMARY_COLOR, BG_COLOR = (34, 49, 63), (236, 240, 241)
    lang = 'en' if 'full_name' in data else 'pt'
    
    # --- Coluna da Esquerda (Barra Lateral) ---
    pdf.set_fill_color(*PRIMARY_COLOR); pdf.rect(0, 0, 75, 297, 'F')
    pdf.set_text_color(255, 255, 255)
    
    # Nome e Cargo na Barra Lateral
    pdf.set_xy(10, 25)
    pdf.set_font(pdf.font_bold, 'B', 22); pdf.multi_cell(65, 10, data.get('nome_completo', ''), 0, 'C')
    pdf.set_font(pdf.font_regular, 'I', 12); pdf.set_x(10); pdf.cell(65, 10, data.get('cargo', ''), 0, 1, 'C')
    pdf.set_x(10); pdf.line(15, pdf.get_y()+5, 70, pdf.get_y()+5); pdf.ln(15)

    def add_sidebar_section(title, content_list, is_contact=False):
        if not content_list: return
        pdf.set_x(10); pdf.set_font(pdf.font_bold, 'B', 12); pdf.cell(65, 8, title.upper(), 0, 1, 'L'); pdf.ln(2)
        pdf.set_font(pdf.font_regular, '', 9)
        for item in content_list:
            if item:
                pdf.set_x(12); pdf.multi_cell(60, 5, item, 0, 'L')
        pdf.ln(8)

    contact_list = [
        f"📍 {data.get('cidade_estado', '')}",
        f"📞 {data.get('telefone', '')}",
        f"✉️ {data.get('email', '')}"
    ]
    add_sidebar_section("Contato" if lang == 'pt' else "Contact", [item for item in contact_list if item.split(' ')[-1]])
    add_sidebar_section("Habilidades" if lang == 'pt' else "Skills", [f"• {s}" for s in (data.get('habilidades') or data.get('skills', []))])
    
    # --- Coluna da Direita (Conteúdo Principal) ---
    pdf.set_xy(85, 25); pdf.set_text_color(40, 40, 40)
    
    def add_main_section(title, content):
        if not content or (isinstance(content, str) and ('pular' in content.lower() or 'não informado' in content.lower())): return
        pdf.set_x(85); pdf.set_font(pdf.font_bold, 'B', 14); pdf.cell(0, 8, title.upper(), 0, 1, 'L')
        pdf.set_draw_color(*PRIMARY_COLOR); pdf.line(85, pdf.get_y(), 125, pdf.get_y()); pdf.ln(5)
        pdf.set_font(pdf.font_regular, '', 10); pdf.set_text_color(80, 80, 80)
        
        if isinstance(content, list) and all(isinstance(i, dict) for i in content): # Experiências
            for item in content:
                pdf.set_x(85); pdf.set_font(pdf.font_bold, 'B', 11); pdf.multi_cell(115, 6, f"{item.get('cargo', '')} | {item.get('empresa', '')}", 0, 'L')
                pdf.set_x(85); pdf.set_font(pdf.font_regular, 'I', 9); pdf.set_text_color(120, 120, 120); pdf.multi_cell(115, 5, item.get('periodo', ''), 0, 'L')
                pdf.set_font(pdf.font_regular, '', 10); pdf.set_text_color(80, 80, 80); pdf.set_x(88)
                pdf.multi_cell(110, 5, f"• {item.get('descricao', '')}"); pdf.ln(5)
        elif isinstance(content, list): # Cursos, Formação
             for item in content:
                pdf.set_x(88); pdf.multi_cell(110, 5, f"• {item}")
             pdf.ln(5)
        else: # Resumo
            pdf.set_x(85); pdf.multi_cell(115, 6, content)
        pdf.ln(8)

    title_map_pt = {"resumo": "Sobre Mim", "experiencias": "Experiência Profissional", "formacao": "Formação", "cursos": "Cursos e Certificações"}
    title_map_en = {"professional_summary": "About Me", "work_experience": "Work Experience", "education": "Education", "courses_certifications": "Courses & Certifications"}

    add_main_section(title_map_pt.get('resumo'), data.get('resumo') or data.get('professional_summary'))
    add_main_section(title_map_pt.get('experiencias'), data.get('experiencias') or data.get('work_experience'))
    add_main_section(title_map_pt.get('formacao'), [data.get('formacao') or data.get('education')])
    add_main_section(title_map_pt.get('cursos'), data.get('cursos') or data.get('courses_certifications'))
    
    pdf.output(path)

# ==============================================================================
# --- 7. LÓGICA E FLUXO DA CONVERSA (VERSÃO OSCAR)
# ==============================================================================
CONVERSATION_FLOW = [
    ('nome_completo', 'Legal! Para começar, qual o seu nome completo?'),
    ('cidade_estado', 'Ótimo, {nome}! Agora me diga em qual cidade e estado você mora.'),
    ('telefone', 'Pode me informar um telefone de contato com DDD?'),
    ('email', 'Qual o seu melhor e-mail para contato?'),
    ('resumo', 'Vamos caprichar! Escreva um pequeno resumo sobre você e seus objetivos. (Se não tiver, é só dizer "pular").'),
    ('formacao', 'Qual a sua formação? (Ex: Ensino Médio Completo, Graduação em Administração)'),
    ('habilidades', 'Quais são suas principais habilidades, {nome}? (Ex: Comunicação, Pacote Office). Pode listar várias, separando por vírgula.'),
    ('cursos', 'Você tem algum curso ou certificação? Me conte um por um. Quando acabar, digite "pronto".')
]
REVIEW_KEY_MAP = {
    'nome_completo': 'Nome', 'cidade_estado': 'Cidade/Estado', 'telefone': 'Telefone',
    'email': 'E-mail', 'cargo': 'Cargo Principal', 'resumo': 'Resumo',
    'experiencias': 'Experiências', 'formacao': 'Formação', 'habilidades': 'Habilidades', 'cursos': 'Cursos'
}
REVIEW_ORDER = ['nome_completo', 'cidade_estado', 'telefone', 'email', 'cargo', 'resumo', 'formacao', 'habilidades', 'cursos', 'experiencias']

state_handlers = {}
def handle_state(state):
    def decorator(func):
        state_handlers[state] = func
        return func
    return decorator

def show_payment_options(phone):
    """Exibe as opções de plano para o usuário."""
    message = f"""Certo, vamos escolher seu plano. Você terá acesso a 3 modelos de currículo (Moderno, Clássico e Criativo) e poderá editar quantas vezes quiser antes de finalizar.

*Plano Básico - R$ {PRECO_BASICO:.2f}*
📄 1 Currículo em Português (PDF)
✨ Otimização com IA (opcional)
💬 Perguntas para Entrevista
(Válido para {CREDITOS_BASICO} currículos)

*Plano Premium - R$ {PRECO_PREMIUM:.2f}*
📄 1 Currículo em Português
🇺🇸 1 Versão em Inglês
✨ Otimização com IA
💬 Perguntas para Entrevista
(Válido para {CREDITOS_PREMIUM} currículos)

*Revisão Humana - R$ {PRECO_REVISAO_HUMANA:.2f}*
⭐ Tudo do Premium + Revisão por um especialista de RH.

*Assinatura Mensal - R$ {PRECO_ASSINATURA:.2f}*
👑 Currículos ilimitados, versões em inglês e todos os benefícios enquanto for assinante!

Qual plano você prefere? (*básico*, *premium*, *revisão* ou *assinatura*)"""
    send_whatsapp_message(phone, message)
    update_user(phone, {'state': 'awaiting_plan_choice'})

def show_review_menu(phone, resume_data):
    """Exibe o menu de revisão com os dados atuais do currículo."""
    review_text = "Tudo pronto! 🎉\n\nVamos revisar as informações antes de finalizar. Veja como ficou:\n\n"
    for i, key in enumerate(REVIEW_ORDER):
        value = resume_data.get(key, 'Não preenchido')
        label = REVIEW_KEY_MAP.get(key, key.replace('_', ' ').capitalize())
        
        display_value = value
        if key == 'experiencias':
            review_text += f"*{i+1}. {label}:*\n"
            if isinstance(value, list) and value:
                for exp in value:
                    review_text += f"  - {exp.get('cargo', '')} em {exp.get('empresa', '')} ({exp.get('periodo', 'sem período')})\n"
            else:
                review_text += "  Nenhum item adicionado\n"
            continue
            
        if isinstance(value, list):
            display_value = ", ".join(map(str, value)) if value else "Nenhum item adicionado"
        
        if isinstance(display_value, str) and len(display_value) > 100:
            display_value = display_value[:100] + "..."
            
        review_text += f"*{i+1}. {label}:* {display_value}\n"

    review_text += "\nSe precisar corrigir algo, é só me dizer o *número* do item. Se estiver tudo certo, digite *'finalizar'* para irmos ao pagamento."
    send_whatsapp_message(phone, review_text)
    update_user(phone, {'state': 'awaiting_review_choice', 'editing_field': None})

def go_to_next_step(phone, resume_data, current_idx):
    user_name = resume_data.get('nome_completo', '').split(' ')[0].capitalize()
    if current_idx + 1 < len(CONVERSATION_FLOW):
        next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
        next_question = next_question.format(nome=user_name)
        send_whatsapp_message(phone, next_question)
        update_user(phone, {'state': f'flow_{next_key}'})
    else:
        update_user(phone, {'state': 'awaiting_experience_job_title', 'current_experience': json.dumps({})})
        send_whatsapp_message(phone, f"Ótimo, {user_name}. Agora vamos adicionar suas experiências profissionais, começando pela mais recente. Se não tiver, é só dizer 'pular'. Qual foi seu cargo?")

# --- Handlers de Estado ---

@handle_state('awaiting_welcome')
def handle_welcome(user, message_data):
    send_whatsapp_message(user['phone'], f"Olá! Eu sou o {BOT_NAME} 🤖, seu novo assistente de carreira. Vou te ajudar a criar um currículo profissional incrível!")
    show_payment_options(user['phone'])

@handle_state('awaiting_plan_choice')
def handle_plan_choice(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    plan_map = {
        'basico': {'name': 'basico', 'credits': CREDITOS_BASICO}, 'básico': {'name': 'basico', 'credits': CREDITOS_BASICO},
        'premium': {'name': 'premium', 'credits': CREDITOS_PREMIUM},
        'assinatura': {'name': 'assinatura', 'credits': CREDITOS_ASSINATURA},
        'revisao': {'name': 'revisao_humana', 'credits': 1}, 'revisão': {'name': 'revisao_humana', 'credits': 1}, 'humana': {'name': 'revisao_humana', 'credits': 1}
    }
    chosen_plan = next((value for key, value in plan_map.items() if key in choice), None)
    if chosen_plan:
        update_data = {'plan': chosen_plan['name'], 'credits': chosen_plan['credits'], 'state': 'choosing_template'}
        update_user(phone, update_data)
        send_whatsapp_message(phone, "Ótima escolha! Agora, vamos escolher o visual do seu currículo:\n\n1. *Moderno*\n2. *Clássico*\n3. *Criativo*\n\nÉ só me dizer o número ou o nome.")
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Por favor, escolha *básico*, *premium*, *assinatura* ou *revisão*.")

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone, message = user['phone'], message_data.get('text', '').lower().strip()
    template_map = {'1': 'moderno', 'moderno': 'moderno', '2': 'classico', 'clássico': 'classico', '3': 'criativo', 'criativo': 'criativo'}
    chosen_template = template_map.get(message, None)
    if chosen_template:
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
        
        if message.lower().strip() in PULAR_COMMANDS and current_key == 'resumo':
            extracted_info = "Não informado"
        elif message.lower().strip() in PRONTO_COMMANDS and current_key == 'cursos':
            go_to_next_step(phone, resume_data, current_step_index)
            return
        else:
            extracted_info = extract_and_format_info(current_key, current_question, message)
        
        if current_key in ['habilidades', 'cursos']:
            if not resume_data.get(current_key): resume_data[current_key] = []
            if current_key == 'habilidades':
                resume_data[current_key].extend([format_text(current_key, h) for h in extracted_info.split(',')])
            else:
                resume_data[current_key].append(extracted_info)
            if current_key == 'cursos':
                send_whatsapp_message(phone, 'Curso adicionado. Me diga o próximo ou digite "pronto" para finalizar.')
                update_user(phone, {'resume_data': json.dumps(resume_data)}); return
        else:
            resume_data[current_key] = extracted_info
            
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        go_to_next_step(phone, resume_data, current_step_index)

for i in range(len(CONVERSATION_FLOW)): create_flow_handler(i)

@handle_state('awaiting_experience_job_title')
def handle_exp_job_title(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    if message.lower().strip() in PULAR_COMMANDS:
        show_review_menu(phone, json.loads(user['resume_data'])); return
    
    cargo = extract_and_format_info('cargo', "Qual foi seu cargo?", message)
    current_experience = {'cargo': cargo}
    update_user(phone, {'state': 'awaiting_experience_company', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Entendido. E o nome da empresa?")

@handle_state('awaiting_experience_company')
def handle_exp_company(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    empresa = extract_and_format_info('empresa', "Qual o nome da empresa?", message)
    current_experience = json.loads(user['current_experience'])
    current_experience['empresa'] = empresa
    update_user(phone, {'state': 'awaiting_experience_period', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Anotado. Qual foi o período? (Ex: 2020 - 2022 ou Jan 2021 - Dez 2022)")

@handle_state('awaiting_experience_period')
def handle_exp_period(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    periodo = extract_and_format_info('periodo', "Qual foi o período?", message)
    current_experience = json.loads(user['current_experience'])
    current_experience['periodo'] = periodo
    update_user(phone, {'state': 'awaiting_experience_description', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Ok. Agora descreva brevemente suas responsabilidades e conquistas nesse cargo.")

@handle_state('awaiting_experience_description')
def handle_exp_description(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    descricao = extract_and_format_info('descricao', "Descreva suas responsabilidades.", message)
    current_experience = json.loads(user['current_experience'])
    current_experience['descricao'] = descricao
    resume_data = json.loads(user['resume_data'])
    
    if 'experiencias' not in resume_data or not isinstance(resume_data['experiencias'], list): resume_data['experiencias'] = []
    resume_data['experiencias'].insert(0, current_experience) # Adiciona no início
    
    # Define o cargo principal do currículo com base na primeira experiência adicionada
    if not resume_data.get('cargo'):
        resume_data['cargo'] = current_experience.get('cargo')
        logging.info(f"Cargo principal definido como: {resume_data['cargo']}")

    update_user(phone, {'state': 'awaiting_another_experience', 'resume_data': json.dumps(resume_data)})
    send_whatsapp_message(phone, "Experiência adicionada! Deseja adicionar outra? (Responda com *sim* ou *não*)")

@handle_state('awaiting_another_experience')
def handle_another_experience(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    if choice == 'sim':
        update_user(phone, {'state': 'awaiting_experience_job_title', 'current_experience': json.dumps({})})
        send_whatsapp_message(phone, "Vamos lá. Qual era o seu cargo na próxima experiência?")
    else:
        update_user(phone, {'state': 'awaiting_improve_choice'})
        send_whatsapp_message(phone, "Ok, terminamos as experiências. Gostaria que eu usasse IA para reescrever suas descrições de forma mais profissional? (Responda com *sim* ou *não*)")

@handle_state('awaiting_improve_choice')
def handle_improve_choice(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    resume_data = json.loads(user['resume_data'])
    if choice == 'sim' and resume_data.get('experiencias'):
        send_whatsapp_message(phone, "Excelente! Deixa comigo, estou otimizando seus textos... ✍️ Isso pode levar um instante.")
        improved_experiences = improve_experience_descriptions(resume_data.get('experiencias', []))
        if improved_experiences: resume_data['experiencias'] = improved_experiences
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        send_whatsapp_message(phone, "Prontinho! Textos melhorados.")
    else:
        send_whatsapp_message(phone, "Sem problemas! Vamos para a revisão final.")
    show_review_menu(phone, resume_data)

@handle_state('awaiting_review_choice')
def handle_review_choice(user, message_data):
    phone, message = user['phone'], message_data.get('text', '').lower().strip()
    if message in ['finalizar', 'pagar', 'tudo certo', 'ok']:
        prices = {'basico': PRECO_BASICO, 'premium': PRECO_PREMIUM, 'revisao_humana': PRECO_REVISAO_HUMANA, 'assinatura': PRECO_ASSINATURA}
        price = prices.get(user['plan'], 0.0)
        send_whatsapp_message(phone, f"Ótimo! Para o plano *{user['plan'].replace('_', ' ').capitalize()}* (R$ {price:.2f}), pague com o PIX abaixo:")
        send_whatsapp_message(phone, PIX_PAYLOAD_STRING)
        send_whatsapp_message(phone, "Depois de pagar, é só me enviar a *foto do comprovante* que eu libero seus arquivos! ✨")
        update_user(phone, {'state': 'awaiting_payment_proof'})
        return
    if message.isdigit() and 1 <= int(message) <= len(REVIEW_ORDER):
        item_index = int(message) - 1
        field_to_edit = REVIEW_ORDER[item_index]
        # Pergunta genérica para edição
        question_to_ask = f"Ok, vamos corrigir seu *{REVIEW_KEY_MAP[field_to_edit]}*. Por favor, me envie a informação correta."
        update_user(phone, {'state': 'awaiting_correction_input', 'editing_field': field_to_edit})
        send_whatsapp_message(phone, question_to_ask)
    else:
        send_whatsapp_message(phone, "Não entendi. Por favor, envie o número do item que quer corrigir ou digite 'finalizar'.")

@handle_state('awaiting_correction_input')
def handle_correction_input(user, message_data):
    phone, message, field_to_edit = user['phone'], message_data.get('text', ''), user['editing_field']
    if not field_to_edit:
        handle_default(user, message_data); return
    
    resume_data = json.loads(user['resume_data'])
    # Usa a mesma função de formatação para a correção
    question = f"Qual o(a) {REVIEW_KEY_MAP[field_to_edit]} correto(a)?"
    corrected_info = extract_and_format_info(field_to_edit, question, message)
    resume_data[field_to_edit] = corrected_info
    
    update_user(phone, {'resume_data': json.dumps(resume_data), 'editing_field': None, 'state': 'awaiting_review_choice'})
    # Mostra o menu de revisão atualizado
    show_review_menu(phone, resume_data)

@handle_state('awaiting_payment_proof')
def handle_payment_proof(user, message_data):
    phone = user['phone']
    if 'image' in message_data and 'url' in message_data['image']:
        image_url = message_data['image']['url']
        send_whatsapp_message(phone, "Oba, recebi seu comprovante! 🕵️‍♂️ Analisando com a IA, só um segundo...")
        analysis = analyze_pix_receipt(image_url)
        if analysis and analysis.get('verified'):
            send_whatsapp_message(phone, "Pagamento confirmado! ✅ Já estou preparando seus arquivos e te envio em instantes...")
            user_data_to_pass = dict(user)
            update_data = {'payment_verified': 1, 'state': 'delivering', 'payment_timestamp': datetime.now()}
            if user_data_to_pass['plan'] == 'assinatura':
                update_data['subscription_valid_until'] = datetime.now() + timedelta(days=30)
            update_user(phone, update_data)
            user_data_to_pass.update(update_data)
            run_long_task_in_background(target_func=deliver_final_product, args=(user_data_to_pass,))
        else:
            send_whatsapp_message(phone, "Hmm, não consegui confirmar o pagamento para o nome correto. Tente enviar uma imagem mais nítida do comprovante.")
    else:
        send_whatsapp_message(phone, "Ainda não recebi a imagem. É só me enviar a foto do comprovante de pagamento.")

@handle_state('awaiting_interview_prep_choice')
def handle_interview_prep(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    if choice == 'sim':
        send_whatsapp_message(phone, "Ótima ideia! Analisando seu perfil para criar as melhores perguntas... 🧠")
        resume_data = json.loads(user['resume_data'])
        questions = generate_interview_questions(resume_data)
        if questions: send_whatsapp_message(phone, f"Aqui estão algumas perguntas para você treinar:\n\n{questions}")
        send_whatsapp_message(phone, "Boa sorte na sua preparação! 🚀")
    else:
        send_whatsapp_message(phone, "Entendido! Sem problemas. Muito sucesso na sua jornada! 🚀")
    update_user(phone, {'state': 'completed'})

@handle_state('completed')
def handle_completed(user, message_data):
    send_whatsapp_message(user['phone'], f"Olá! Eu sou o {BOT_NAME}. Já finalizamos seu currículo. Se precisar criar um novo ou usar seus benefícios, digite 'oi' para ver as opções! 😉")

def handle_default(user, message_data=None):
    phone = user['phone']
    if user.get('plan') == 'assinatura' and user.get('subscription_valid_until'):
        try:
            valid_until = datetime.fromisoformat(user['subscription_valid_until'])
            if datetime.now() < valid_until:
                days_left = (valid_until - datetime.now()).days
                send_whatsapp_message(phone, f"Olá de novo! Sua assinatura está ativa por mais {days_left} dias. 👍\nVamos criar uma nova versão do seu currículo.")
                update_user(phone, {'state': 'choosing_template', 'resume_data': json.dumps({'cargo': ''})})
                send_whatsapp_message(phone, "Qual dos 3 templates você gostaria de usar desta vez?")
                return
        except (TypeError, ValueError):
            logging.error(f"Timestamp inválido para assinante {phone}")
    
    update_user(phone, {
        'state': 'awaiting_welcome', 'resume_data': json.dumps({'cargo': ''}), 'plan': 'none', 
        'template': 'none', 'payment_verified': 0, 'payment_timestamp': None, 
        'credits': 0, 'subscription_valid_until': None, 'current_experience': json.dumps({}), 'editing_field': None
    })
    handle_welcome({'phone': phone}, message_data)

def deliver_final_product(user_data, test_data=None, debug=False):
    with app.app_context():
        phone, plan, template = user_data['phone'], user_data['plan'], user_data['template']
        resume_data = test_data if test_data else json.loads(user_data['resume_data'])
        
        if plan != 'assinatura' and not debug and user_data.get('credits', 0) < 1:
            send_whatsapp_message(phone, "Você não tem mais créditos. Digite 'oi' para ver os planos.")
            update_user(phone, {'state': 'awaiting_welcome'}); return
        
        send_whatsapp_message(phone, "Preparando seu currículo principal...")
        pdf_path = os.path.join(TEMP_DIR, f"Curriculo_{resume_data.get('nome_completo', 'user').replace(' ', '_')}.pdf")
        generate_resume_pdf(resume_data, template, pdf_path)
        send_whatsapp_document(phone, pdf_path, os.path.basename(pdf_path), "Seu currículo novinho em folha!")
        
        if plan in ['premium', 'revisao_humana', 'assinatura']:
            send_whatsapp_message(phone, "Gerando sua versão em Inglês...")
            english_data = translate_resume_data_to_english(resume_data)
            if english_data:
                english_pdf_path = os.path.join(TEMP_DIR, f"Resume_{english_data.get('full_name', 'user').replace(' ', '_')}.pdf")
                generate_resume_pdf(english_data, template, english_pdf_path)
                send_whatsapp_document(phone, english_pdf_path, os.path.basename(english_pdf_path), "Aqui está sua versão em Inglês!")
                os.remove(english_pdf_path)
        
        if plan == 'revisao_humana':
            send_whatsapp_message(ADMIN_PHONE_NUMBER, f"Nova revisão solicitada!\n\nCliente: {resume_data.get('nome_completo')}\nTelefone: {phone}\nPlano: Revisão Humana")
            send_whatsapp_document(ADMIN_PHONE_NUMBER, pdf_path, f"REVISAR_{os.path.basename(pdf_path)}")
            send_whatsapp_message(phone, "Sua solicitação de revisão foi enviada para nossa equipe! Em até 24h úteis um especialista entrará em contato. 👨‍💼")
        
        os.remove(pdf_path)
        
        if plan != 'assinatura' and not debug:
            new_credits = user_data['credits'] - 1
            update_user(phone, {'credits': new_credits})
            send_whatsapp_message(phone, f"Crédito utilizado! Você ainda tem {new_credits} crédito(s).")
            
        update_user(phone, {'state': 'awaiting_interview_prep_choice'})
        send_whatsapp_message(phone, "Seus arquivos foram entregues! 📄✨\n\nComo um bônus final, gostaria de gerar uma lista de perguntas de entrevista com base no seu currículo? (Responda com *sim* ou *não*)")

# ==============================================================================
# --- 8. WEBHOOK E INICIALIZAÇÃO
# ==============================================================================
def process_message(phone, message_data):
    message_text = message_data.get('text', '').lower().strip()
    user = get_user(phone)

    if not user or message_text in REINICIAR_COMMANDS:
        user_info = user if user else {'phone': phone}
        handle_default(user_info, message_data)
        return

    state = user['state']
    handler = state_handlers.get(state)

    if handler:
        logging.info(f"Direcionando usuário {phone} (estado: {state}) para o handler: {handler.__name__}")
        handler(user, message_data)
    else:
        logging.warning(f"Nenhum handler encontrado para o estado '{state}' do usuário {phone}. Redirecionando para o default.")
        handle_default(user, message_data)

@app.route('/')
def health_check():
    return "Cadu está no ar! Versão PRO.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"Webhook recebido: {json.dumps(data, indent=2)}")
        
        phone = data.get('phone')
        message_data = {}
        if data.get('text') and isinstance(data['text'], dict) and 'message' in data['text']:
            message_data['text'] = data['text']['message']
        elif data.get('text') and isinstance(data['text'], str):
             message_data['text'] = data['text']
        elif data.get('type') == 'image' and data.get('imageUrl'):
             message_data['image'] = {'url': data['imageUrl']}
        elif 'image' in data and isinstance(data.get('image'), dict) and 'imageUrl' in data['image']:
             message_data['image'] = {'url': data['image']['imageUrl']}

        if phone and message_data:
            process_message(phone, message_data)
        else:
            logging.warning(f"Webhook de {phone} recebido sem dados de mensagem válidos.")
            
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logging.error(f"Erro crítico no webhook: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def check_abandoned_sessions():
    with app.app_context():
        logging.info("Verificando sessões abandonadas...")
        conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        time_limit = datetime.now() - timedelta(hours=24)
        cursor.execute("SELECT * FROM users WHERE last_interaction < ? AND state NOT IN ('completed', 'reminded', 'delivering')", (time_limit,))
        abandoned_users = cursor.fetchall()
        for user in abandoned_users:
            logging.info(f"Enviando lembrete para: {user['phone']}")
            message = f"Olá, {BOT_NAME} passando para dar um oi! 👋 Vi que começamos a montar seu currículo mas não terminamos. Que tal continuarmos de onde paramos? É só responder a última pergunta!"
            send_whatsapp_message(user['phone'], message)
            update_user(user['phone'], {'state': 'reminded'})
        conn.close()

init_database()
if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_abandoned_sessions, 'interval', hours=6)
    scheduler.start()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
