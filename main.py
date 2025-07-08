# -*- coding: utf-8 -*-
# VERSÃO FINAL - 3 TEMPLATES ÚNICOS, FLUXO COMPLETO E MODO DE TESTE

# ==============================================================================
# --- IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
# ==============================================================================
import os
import sqlite3
import json
import base64
import logging
import random
from datetime import datetime, timedelta
import requests
import openai
from flask import Flask, request, jsonify
from fpdf import FPDF
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# --- INICIALIZAÇÃO E CONFIGURAÇÕES GLOBAIS
# ==============================================================================
app = Flask(__name__)
BOT_NAME = "Cadu"

# --- MODO DE TESTE ---
# Adicione números de telefone aqui para ativar o modo de teste, que gera todos os PDFs.
DEBUG_PHONE_NUMBERS = ["555195995888", "555199864475"]

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

# --- CONFIGS DE PAGAMENTO ---
PIX_RECIPIENT_NAME = "Leonardo Maciel Abbadi"
PIX_PAYLOAD_STRING = "00020126580014br.gov.bcb.pix0136fd3412eb-9577-41ea-ba4d-12293570c0155204000053039865802BR5922Leonardo Maciel Abbadi6008Brasilia62240520daqr1894289448628220630439D1"
PRECO_BASICO, PRECO_PREMIUM, PRECO_REVISAO_HUMANA = 9.99, 10.99, 15.99

# --- CAMINHOS DE ARQUIVOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('RENDER_DISK_PATH', SCRIPT_DIR)
DATABASE_FILE = os.path.join(DATA_DIR, 'cadu_database.db')
FONT_DIR = os.path.join(SCRIPT_DIR, 'fonts')
TEMP_DIR = "/tmp"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

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
            payment_verified INTEGER DEFAULT 0, last_interaction TIMESTAMP,
            current_experience TEXT
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
            'last_interaction': datetime.now(), 'current_experience': json.dumps({})
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
    payload = {"phone": phone, "document": f"data:application/pdf;base64,{doc_base64}", "fileName": filename, "caption": caption}
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
        completion = openai.chat.completions.create(model=model_to_use, messages=prompt_messages, temperature=0.7, response_format=response_format)
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Erro na API da OpenAI: {e}")
        return "Tive um problema para processar sua resposta. Vamos tentar de novo."

def extract_info_from_message(question, user_message):
    system_prompt = "Você é um assistente que extrai a informação principal da resposta de um usuário, sem frases extras. Ex: se a pergunta é 'Qual seu nome?' e a resposta é 'meu nome é joão da silva', extraia 'joão da silva'. Se a resposta for 'não quero informar', extraia 'Não informado'."
    user_prompt = f'Pergunta: "{question}"\nResposta: "{user_message}"\n\nInformação extraída:'
    return get_openai_response([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])

def analyze_pix_receipt(image_url):
    system_prompt = f'Analise a imagem de um comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}". Responda APENAS com um objeto JSON com as chaves "verified" (true/false). Não inclua a formatação markdown ```json```.'
    messages = [{"role": "user", "content": [{"type": "text", "text": system_prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
    try:
        json_response_str = get_openai_response(messages, is_json=True)
        return json.loads(json_response_str)
    except Exception as e:
        logging.error(f"Erro ao analisar comprovante PIX com OpenAI: {e}", exc_info=True)
        return {'verified': False}

def translate_resume_data_to_english(resume_data):
    system_prompt = "Você é um tradutor especialista em currículos. Traduza o seguinte JSON de dados de um currículo do português para o inglês profissional. Traduza tanto as chaves (keys) quanto os valores (values) para o inglês. Use estas chaves em inglês: 'full_name', 'city_state', 'phone', 'email', 'desired_role', 'professional_summary', 'work_experience', 'education', 'skills', 'courses_certifications'. O valor de 'work_experience' e 'courses_certifications' devem ser uma lista de dicionários, traduza o conteúdo dentro deles também."
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
    system_prompt = "Você é um especialista em RH que otimiza currículos. Reescreva a lista de experiências profissionais a seguir para que foquem em resultados e ações, usando verbos de impacto. Transforme responsabilidades em conquistas. Mantenha a estrutura de lista de dicionários. Retorne apenas o JSON."
    user_prompt = f"Experiências originais: {json.dumps(experiences, ensure_ascii=False)}\n\nReescreva as descrições de forma profissional e focada em resultados (retorne apenas a lista em JSON):"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    response_str = get_openai_response(messages, is_json=True)
    try:
        response_data = json.loads(response_str)
        if isinstance(response_data, dict) and 'work_experience' in response_data:
            return response_data['work_experience']
        elif isinstance(response_data, list):
            return response_data
        return experiences
    except:
        return experiences

def generate_interview_questions(resume_data):
    system_prompt = "Você é um recrutador sênior preparando uma entrevista para a vaga de '{cargo}'. Com base no currículo do candidato, crie uma lista de 5 a 7 perguntas de entrevista perspicazes e relevantes, misturando perguntas comportamentais (STAR: Situação, Tarefa, Ação, Resultado) e técnicas baseadas nas experiências e habilidades listadas. Formate a resposta como um texto único, com cada pergunta numerada."
    user_prompt = f"Currículo do candidato:\n{json.dumps(resume_data, indent=2, ensure_ascii=False)}\n\nListe as perguntas para a entrevista:"
    return get_openai_response([{"role": "system", "content": system_prompt.format(cargo=resume_data.get('cargo', ''))}, {"role": "user", "content": user_prompt}])

# ==============================================================================
# --- GERAÇÃO DE PDF
# ==============================================================================
class PDF(FPDF):
    def add_font_setup(self):
        try:
            self.add_font('DejaVu', '', os.path.join(FONT_DIR, 'DejaVuSans.ttf'), uni=True)
            self.add_font('DejaVu', 'B', os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'), uni=True)
            self.add_font('DejaVu', 'I', os.path.join(FONT_DIR, 'DejaVuSans-Oblique.ttf'), uni=True)
            self.add_font('DejaVu', 'BI', os.path.join(FONT_DIR, 'DejaVuSans-BoldOblique.ttf'), uni=True)
            self.font_regular = 'DejaVu'
            self.font_bold = 'DejaVu'
        except RuntimeError as e:
            logging.error(f"ERRO DE FONTE: {e}. Verifique se a pasta 'fonts' e os 4 arquivos .ttf estão no seu GitHub.")
            self.font_regular = 'Helvetica'
            self.font_bold = 'Helvetica'
        self.set_font(self.font_regular, '', 10)

def generate_resume_pdf(data, template_choice, path):
    templates = {
        'moderno': generate_template_moderno,
        'classico': generate_template_classico,
        'criativo': generate_template_criativo
    }
    pdf_function = templates.get(template_choice, generate_template_moderno)
    pdf_function(data, path)

def generate_simple_text_pdf(text, path):
    pdf = PDF()
    pdf.add_font_setup()
    pdf.add_page()
    pdf.set_font(pdf.font_regular, '', 11)
    pdf.multi_cell(0, 7, text)
    pdf.output(path)

# --- NOVOS TEMPLATES DE CURRÍCULO ---

def generate_template_moderno(data, path):
    pdf = PDF()
    pdf.add_font_setup()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    SIDEBAR_COLOR, ACCENT_COLOR = (45, 52, 54), (26, 188, 156)

    pdf.set_fill_color(*SIDEBAR_COLOR)
    pdf.rect(0, 0, 70, 297, 'F')
    pdf.set_xy(10, 20)
    pdf.set_text_color(255, 255, 255)

    lang = 'en' if 'full_name' in data else 'pt'

    def add_sidebar_section(title, content):
        if not content or not str(content).strip(): return
        pdf.set_x(10)
        pdf.set_font(pdf.font_bold, 'B', 11)
        pdf.cell(55, 10, title.upper(), 0, 1)
        pdf.set_font(pdf.font_regular, '', 9)
        if isinstance(content, list): content = "\n".join([f"• {item}" for item in content])
        pdf.multi_cell(55, 5, content)
        pdf.ln(5)

    contact_info = f"{data.get('email', '')}\n{data.get('telefone') or data.get('phone')}\n{data.get('cidade_estado') or data.get('city_state')}"
    add_sidebar_section("Contato" if lang == 'pt' else "Contact", contact_info)
    add_sidebar_section("Formação" if lang == 'pt' else "Education", data.get('formacao') or data.get('education'))
    add_sidebar_section("Habilidades" if lang == 'pt' else "Skills", data.get('habilidades') or data.get('skills'))

    pdf.set_xy(80, 15)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font(pdf.font_bold, 'B', 26)
    pdf.multi_cell(120, 11, data.get('nome_completo') or data.get('full_name'))
    pdf.set_font(pdf.font_regular, '', 14)
    pdf.set_text_color(108, 122, 137)
    pdf.set_x(80)
    pdf.cell(0, 8, data.get('cargo') or data.get('desired_role'), 0, 1, 'L')
    pdf.ln(8)

    def add_right_section(title, content):
        if content and str(content).strip() and 'pular' not in str(content).lower() and 'não informado' not in str(content).lower():
            pdf.set_x(80)
            pdf.set_font(pdf.font_bold, 'B', 12)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(0, 8, title.upper(), 0, 1, 'L')
            pdf.set_draw_color(*ACCENT_COLOR)
            pdf.line(80, pdf.get_y(), 120, pdf.get_y())
            pdf.ln(4)
            pdf.set_font(pdf.font_regular, '', 10)
            pdf.set_text_color(80, 80, 80)
            if isinstance(content, list) and all(isinstance(i, dict) for i in content):
                for item in content:
                    pdf.set_x(80)
                    pdf.set_font(pdf.font_bold, 'B', 10)
                    pdf.multi_cell(120, 6, f"{item.get('cargo', item.get('title', ''))} | {item.get('empresa', item.get('company', ''))}", 0, 'L')
                    pdf.set_font(pdf.font_regular, 'I', 9)
                    pdf.set_x(80)
                    pdf.cell(0, 6, item.get('periodo', item.get('period', '')), 0, 1)
                    pdf.set_font(pdf.font_regular, '', 10)
                    pdf.set_x(85)
                    pdf.multi_cell(115, 5, f"• {item.get('descricao', item.get('description', ''))}")
                    pdf.ln(3)
            elif isinstance(content, list):
                pdf.set_x(80)
                pdf.multi_cell(120, 6, "\n".join([f"• {item}" for item in content]))
            else:
                pdf.set_x(80)
                pdf.multi_cell(120, 6, content)
            pdf.ln(4)

    title_map_pt = {"resumo": "Resumo Profissional", "experiencias": "Experiência Profissional", "cursos": "Cursos e Certificações"}
    title_map_en = {"professional_summary": "Professional Summary", "work_experience": "Work Experience", "courses_certifications": "Courses & Certifications"}

    add_right_section(title_map_pt.get('resumo') if lang == 'pt' else title_map_en.get('professional_summary'), data.get('resumo') or data.get('professional_summary'))
    add_right_section(title_map_pt.get('experiencias') if lang == 'pt' else title_map_en.get('work_experience'), data.get('experiencias') or data.get('work_experience'))
    add_right_section(title_map_pt.get('cursos') if lang == 'pt' else title_map_en.get('courses_certifications'), data.get('cursos') or data.get('courses_certifications'))
    pdf.output(path)

def generate_template_classico(data, path):
    pdf = PDF()
    pdf.add_font_setup()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    lang = 'en' if 'full_name' in data else 'pt'

    pdf.set_font(pdf.font_bold, 'B', 24)
    pdf.cell(0, 12, data.get('nome_completo') or data.get('full_name'), 0, 1, 'C')
    pdf.set_font(pdf.font_regular, '', 11)
    contato = f"{data.get('email', '')} | {data.get('telefone') or data.get('phone')} | {data.get('cidade_estado') or data.get('city_state')}"
    pdf.cell(0, 8, contato, 0, 1, 'C')
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    def add_section(title, content):
        if content and str(content).strip() and 'pular' not in str(content).lower() and 'não informado' not in str(content).lower():
            pdf.set_font(pdf.font_bold, 'B', 12)
            pdf.cell(0, 8, title.upper(), 0, 1, 'L')
            pdf.set_font(pdf.font_regular, '', 10)
            if isinstance(content, list) and all(isinstance(i, dict) for i in content):
                for item in content:
                    pdf.set_font(pdf.font_bold, 'B', 10)
                    pdf.cell(0, 6, f"{item.get('cargo', item.get('title', ''))}, {item.get('empresa', item.get('company', ''))}", 0, 1)
                    pdf.set_font(pdf.font_regular, 'I', 9)
                    pdf.cell(0, 5, item.get('periodo', item.get('period', '')), 0, 1)
                    pdf.set_font(pdf.font_regular, '', 10)
                    pdf.multi_cell(0, 5, f"  • {item.get('descricao', item.get('description', ''))}")
                    pdf.ln(3)
            elif isinstance(content, list):
                pdf.multi_cell(0, 5, "\n".join([f"• {item}" for item in content]))
            else:
                pdf.multi_cell(0, 5, content)
            pdf.ln(4)

    title_map_pt = {"resumo": "Resumo", "experiencias": "Experiência Profissional", "formacao": "Formação Acadêmica", "habilidades": "Habilidades", "cursos": "Cursos"}
    title_map_en = {"professional_summary": "Summary", "work_experience": "Work Experience", "education": "Education", "skills": "Skills", "courses_certifications": "Courses"}

    add_section(title_map_pt.get('resumo') if lang == 'pt' else title_map_en.get('professional_summary'), data.get('resumo') or data.get('professional_summary'))
    add_section(title_map_pt.get('experiencias') if lang == 'pt' else title_map_en.get('work_experience'), data.get('experiencias') or data.get('work_experience'))
    add_section(title_map_pt.get('formacao') if lang == 'pt' else title_map_en.get('education'), data.get('formacao') or data.get('education'))
    add_section(title_map_pt.get('habilidades') if lang == 'pt' else title_map_en.get('skills'), data.get('habilidades') or data.get('skills'))
    add_section(title_map_pt.get('cursos') if lang == 'pt' else title_map_en.get('courses_certifications'), data.get('cursos') or data.get('courses_certifications'))
    pdf.output(path)

def generate_template_criativo(data, path):
    pdf = PDF()
    pdf.add_font_setup()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    HEADER_COLOR, ACCENT_COLOR = (211, 84, 0), (230, 126, 34) # Laranja

    pdf.set_fill_color(*HEADER_COLOR)
    pdf.rect(0, 10, 210, 35, 'F')
    pdf.set_y(18)
    pdf.set_font(pdf.font_bold, 'B', 24)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, data.get('nome_completo') or data.get('full_name'), 0, 1, 'C')
    pdf.set_font(pdf.font_regular, '', 12)
    pdf.cell(0, 8, data.get('cargo') or data.get('desired_role'), 0, 1, 'C')

    pdf.set_y(55)
    lang = 'en' if 'full_name' in data else 'pt'
    def add_section(title, content):
        if content and str(content).strip() and 'pular' not in str(content).lower() and 'não informado' not in str(content).lower():
            pdf.set_font(pdf.font_bold, 'B', 12)
            pdf.set_text_color(*HEADER_COLOR)
            pdf.cell(0, 12, title.upper(), 0, 1, 'L')
            pdf.set_font(pdf.font_regular, '', 10)
            pdf.set_text_color(50, 50, 50)
            if isinstance(content, list) and all(isinstance(i, dict) for i in content):
                for item in content:
                    pdf.set_font(pdf.font_bold, 'B', 10)
                    pdf.multi_cell(0, 6, f"{item.get('cargo', item.get('title', ''))} | {item.get('empresa', item.get('company', ''))}", 0, 'L')
                    pdf.set_font(pdf.font_regular, 'I', 9)
                    pdf.cell(0, 6, item.get('periodo', item.get('period', '')), 0, 1)
                    pdf.set_font(pdf.font_regular, '', 10)
                    pdf.multi_cell(0, 5, f"• {item.get('descricao', item.get('description', ''))}")
                    pdf.ln(3)
            elif isinstance(content, list):
                pdf.multi_cell(0, 5, "\n".join([f"• {item}" for item in content]))
            else:
                pdf.multi_cell(0, 5, content)
            pdf.ln(5)

    title_map_pt = {"resumo": "Sobre Mim", "experiencias": "Experiência", "formacao": "Educação", "habilidades": "Competências", "cursos": "Cursos"}
    title_map_en = {"professional_summary": "About Me", "work_experience": "Experience", "education": "Education", "skills": "Skills", "courses_certifications": "Courses"}

    add_section(title_map_pt.get('resumo') if lang == 'pt' else title_map_en.get('professional_summary'), data.get('resumo') or data.get('professional_summary'))
    add_section(title_map_pt.get('experiencias') if lang == 'pt' else title_map_en.get('work_experience'), data.get('experiencias') or data.get('work_experience'))
    add_section(title_map_pt.get('formacao') if lang == 'pt' else title_map_en.get('education'), data.get('formacao') or data.get('education'))
    add_section(title_map_pt.get('habilidades') if lang == 'pt' else title_map_en.get('skills'), data.get('habilidades') or data.get('skills'))
    add_section(title_map_pt.get('cursos') if lang == 'pt' else title_map_en.get('courses_certifications'), data.get('cursos') or data.get('courses_certifications'))
    pdf.output(path)

# ==============================================================================
# --- FLUXO DA CONVERSA
# ==============================================================================
def generate_fake_data():
    first_names, last_names = ["Ana", "Carlos", "Beatriz", "Daniel", "Elisa", "Fernando", "Laura", "Rafael"], ["Silva", "Souza", "Pereira", "Costa", "Rodrigues", "Almeida", "Nunes", "Mendes"]
    jobs = ["Gerente de Projetos", "Analista de Marketing Digital", "Engenheiro de Software", "Designer Gráfico", "Consultor Financeiro", "Arquiteto de Soluções", "Cientista de Dados"]
    companies = ["InovaTech", "Soluções Criativas", "Alpha Systems", "Nexus Digital", "Valor & Cia", "FutureWorks", "DataPrime"]
    skills = ["Liderança de equipes, Metodologias Ágeis, Orçamento", "SEO, Google Ads, Marketing de Conteúdo, Redes Sociais", "Python, JavaScript, React, Docker, AWS", "Adobe Photoshop, Illustrator, UI/UX", "Análise de Investimentos, Modelagem Financeira", "Arquitetura de Cloud, TOGAF", "Machine Learning, Pandas, TensorFlow"]
    name = f"{random.choice(first_names)} {random.choice(last_names)}"
    return {
        "nome_completo": name,
        "cidade_estado": f"{random.choice(['São Paulo, SP', 'Rio de Janeiro, RJ', 'Belo Horizonte, MG', 'Curitiba, PR'])}",
        "telefone": f"+55 ({random.randint(11,55)}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}",
        "email": f"{name.lower().replace(' ','.')}@example.com",
        "cargo": random.choice(jobs),
        "resumo": "Profissional dedicado e proativo com histórico de sucesso em ambientes dinâmicos e desafiadores. Buscando novos desafios para aplicar minhas habilidades técnicas e interpessoais em um ambiente inovador que valorize o crescimento contínuo.",
        "experiencias": [
            {"cargo": random.choice(jobs), "empresa": random.choice(companies), "periodo": "2021 - Presente", "descricao": "Liderou projetos estratégicos de ponta a ponta, gerenciando equipes multifuncionais para entregar soluções inovadoras dentro do prazo e orçamento, resultando em um aumento de 20% na eficiência operacional."},
            {"cargo": "Analista Sênior", "empresa": "DataCorp", "periodo": "2018 - 2021", "descricao": "Desenvolveu dashboards e relatórios analíticos que forneceram insights cruciais para a tomada de decisão da diretoria, levando a uma otimização de custos de 15%."}
        ],
        "formacao": f"Bacharel em {random.choice(['Administração de Empresas', 'Ciência da Computação', 'Design Gráfico', 'Economia'])}",
        "habilidades": random.choice(skills),
        "cursos": ["Certificação Profissional em Gestão de Projetos (PMP)", "Especialização em Liderança e Gestão de Pessoas"]
    }

CONVERSATION_FLOW = [
    ('nome_completo', 'Legal! Para começar, qual o seu nome completo?'),
    ('cidade_estado', 'Ótimo, {nome}! Agora me diga em qual cidade e estado você mora.'),
    ('telefone', 'Pode me informar um telefone de contato com DDD?'),
    ('email', 'Qual o seu melhor e-mail para contato?'),
    ('cargo', 'Certo. Qual o cargo ou área que você está buscando?'),
    ('resumo', 'Vamos caprichar! Escreva um pequeno resumo sobre você e seus objetivos. (Se não tiver, é só dizer "pular").'),
    ('formacao', 'Qual a sua formação? (Ex: Ensino Médio Completo, Graduação em Administração)'),
    ('habilidades', 'Quais são suas principais habilidades? (Ex: Comunicação, Pacote Office). Pode listar várias, separando por vírgula.'),
    ('cursos', 'Você tem algum curso ou certificação? Se sim, me conte um por um. Quando acabar, digite "pronto".')
]
state_handlers = {}
def handle_state(state):
    def decorator(func):
        state_handlers[state] = func
        return func
    return decorator

def process_message(phone, message_data):
    if DEBUG_PHONE_NUMBERS and phone in DEBUG_PHONE_NUMBERS:
        logging.info(f"MODO DE TESTE ATIVADO PARA O NÚMERO: {phone}")
        send_whatsapp_message(phone, "Modo de teste ativado! Gerando todos os modelos de PDFs de exemplo...")
        fake_data = generate_fake_data()
        mock_user = {'phone': phone, 'plan': 'premium'}
        deliver_final_product(mock_user, fake_data, debug=True)
        return

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
    message = f"Para começarmos, conheça nossos planos:\n\n📄 *PLANO BÁSICO - R$ {PRECO_BASICO:.2f}*\n- Currículo em PDF.\n\n✨ *PLANO PREMIUM - R$ {PRECO_PREMIUM:.2f}*\n- Tudo do Básico + Versão em Inglês e Carta de Apresentação.\n\n👨‍💼 *REVISÃO HUMANA - R$ {PRECO_REVISAO_HUMANA:.2f}*\n- Tudo do Premium + Revisão de um especialista.\n\nDigite *básico*, *premium* ou *revisão*."
    send_whatsapp_message(phone, message)
    update_user(phone, {'state': 'awaiting_plan_choice'})

@handle_state('awaiting_plan_choice')
def handle_plan_choice(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    plan_name = None
    if 'básico' in choice or 'basico' in choice: plan_name = 'basico'
    elif 'premium' in choice: plan_name = 'premium'
    elif 'revisão' in choice or 'revisao' in choice or 'humana' in choice: plan_name = 'revisao_humana'

    if plan_name:
        update_user(phone, {'plan': plan_name})
        template_message = "Ótima escolha! Agora, vamos escolher o visual do seu currículo:\n\n1. *Moderno*\n2. *Clássico*\n3. *Criativo*\n\nÉ só me dizer o número ou o nome."
        send_whatsapp_message(phone, template_message)
        update_user(phone, {'state': 'choosing_template'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Escolha *básico*, *premium* ou *revisão*.")

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
        
        extracted_info = ""
        if current_key == 'resumo' and message.lower().strip() in ['pular', 'nao', 'não']:
            extracted_info = "Não informado"
        elif current_key == 'email':
            extracted_info = extract_info_from_message(current_question, message).lower()
        else:
            extracted_info = extract_info_from_message(current_question, message)

        resume_data[current_key] = extracted_info
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        
        go_to_next_step(phone, resume_data, current_step_index)

def go_to_next_step(phone, resume_data, current_idx):
    # Condição para iniciar a coleta de experiência profissional
    if CONVERSATION_FLOW[current_idx][0] == 'resumo':
        update_user(phone, {'state': 'awaiting_experience_job_title', 'current_experience': json.dumps({})})
        send_whatsapp_message(phone, "Ótimo. Agora vamos adicionar suas experiências profissionais, começando pela mais recente. Se não tiver, diga 'pular'. Qual foi seu cargo?")
        return

    # Condição para ir para o próximo passo do fluxo principal
    if current_idx + 1 < len(CONVERSATION_FLOW):
        next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
        
        # Formata a pergunta se necessário
        if '{nome}' in next_question:
            user_name = resume_data.get('nome_completo', '').split(' ')[0]
            next_question = next_question.format(nome=user_name.capitalize())

        send_whatsapp_message(phone, next_question)
        update_user(phone, {'state': f'flow_{next_key}'})
    else: # Fim do fluxo principal de perguntas
        show_review_menu(phone, resume_data)

for i in range(len(CONVERSATION_FLOW)):
    create_flow_handler(i)

@handle_state('awaiting_experience_job_title')
def handle_exp_job_title(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    if message.lower().strip() in ['pular', 'nao', 'não']:
        # Pula toda a seção de experiência
        current_idx = [k for k, q in CONVERSATION_FLOW].index('resumo')
        next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
        send_whatsapp_message(phone, next_question)
        update_user(phone, {'state': f'flow_{next_key}'})
        return
        
    current_experience = {'cargo': message}
    update_user(phone, {'state': 'awaiting_experience_company', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Entendido. E o nome da empresa?")

@handle_state('awaiting_experience_company')
def handle_exp_company(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    current_experience = json.loads(user.get('current_experience', '{}'))
    current_experience['empresa'] = message
    update_user(phone, {'state': 'awaiting_experience_period', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Anotado. Qual foi o período? (Ex: 2020 - 2022, ou Jan 2020 - Dez 2022)")

@handle_state('awaiting_experience_period')
def handle_exp_period(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    current_experience = json.loads(user.get('current_experience', '{}'))
    current_experience['periodo'] = message
    update_user(phone, {'state': 'awaiting_experience_description', 'current_experience': json.dumps(current_experience)})
    send_whatsapp_message(phone, "Ok. Agora descreva brevemente suas responsabilidades e conquistas nesse cargo.")

@handle_state('awaiting_experience_description')
def handle_exp_description(user, message_data):
    phone, message = user['phone'], message_data.get('text', '')
    current_experience = json.loads(user.get('current_experience', '{}'))
    current_experience['descricao'] = message
    
    resume_data = json.loads(user.get('resume_data', '{}'))
    if 'experiencias' not in resume_data:
        resume_data['experiencias'] = []
    resume_data['experiencias'].append(current_experience)
    
    update_user(phone, {'state': 'awaiting_another_experience', 'resume_data': json.dumps(resume_data)})
    send_whatsapp_message(phone, "Experiência adicionada! Deseja adicionar outra? (Responda com *sim* ou *não*)")

@handle_state('awaiting_another_experience')
def handle_another_experience(user, message_data):
    phone, choice = user['phone'], message_data.get('text', '').lower().strip()
    if choice == 'sim':
        update_user(phone, {'state': 'awaiting_experience_job_title', 'current_experience': json.dumps({})})
        send_whatsapp_message(phone, "Vamos lá. Qual era o seu cargo na próxima experiência?")
    else:
        # Após coletar experiências, pergunta sobre a otimização por IA
        send_whatsapp_message(phone, "Ok, terminamos de adicionar suas experiências.")
        update_user(phone, {'state': 'awaiting_improve_choice'})
        send_whatsapp_message(phone, "Gostaria que eu usasse minha IA para reescrever suas experiências de uma forma mais profissional e focada em resultados? (Responda com *sim* ou *não*)")

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
    
    # Continua o fluxo de onde parou (depois da experiência)
    current_idx = [k for k, q in CONVERSATION_FLOW].index('resumo')
    next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
    send_whatsapp_message(phone, next_question)
    update_user(phone, {'state': f'flow_{next_key}'})

def show_review_menu(phone, resume_data):
    review_text = "Antes de finalizar, revise seus dados. Para corrigir, diga o número do item:\n\n"
    # Mapeia chaves internas para nomes amigáveis
    key_map = {
        'nome_completo': 'Nome Completo', 'cidade_estado': 'Cidade/Estado', 'telefone': 'Telefone',
        'email': 'E-mail', 'cargo': 'Cargo Desejado', 'resumo': 'Resumo Profissional',
        'experiencias': 'Experiências', 'formacao': 'Formação', 'habilidades': 'Habilidades', 'cursos': 'Cursos'
    }
    
    flow_keys = [key for key, _ in CONVERSATION_FLOW]
    all_keys_in_order = flow_keys[:6] + ['experiencias'] + flow_keys[6:] # Insere 'experiencias' no lugar certo

    display_data = ""
    for i, key in enumerate(all_keys_in_order):
        friendly_name = key_map.get(key, key.replace('_', ' ').capitalize())
        value = resume_data.get(key, 'Não preenchido')
        
        if key == 'experiencias' and isinstance(value, list):
            exp_text = ""
            for exp in value:
                exp_text += f"\n  - {exp.get('cargo', '')} em {exp.get('empresa', '')}"
            value = exp_text if exp_text else "Nenhuma"
            display_data += f"*{i+1}. {friendly_name}:*{value}\n"
        else:
            display_data += f"*{i+1}. {friendly_name}:* {value}\n"

    review_text += display_data
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
    else:
        # Simplificado para evitar loop de correção complexo
        send_whatsapp_message(phone, "Para corrigir algum dado, por favor reinicie a conversa digitando 'oi'. Se estiver tudo certo, digite 'finalizar'.")

@handle_state('awaiting_payment_proof')
def handle_payment_proof(user, message_data):
    phone = user['phone']
    if 'image' in message_data and 'url' in message_data['image']:
        image_url = message_data['image']['url']
        send_whatsapp_message(phone, "Oba, recebi seu comprovante! 🕵️‍♂️ Analisando com a IA, só um segundo...")
        analysis = analyze_pix_receipt(image_url)
        if analysis.get('verified'):
            send_whatsapp_message(phone, "Pagamento confirmado! ✅")
            send_whatsapp_message(phone, "Estou preparando seus arquivos...")
            update_user(phone, {'payment_verified': 1, 'state': 'delivering'})
            deliver_final_product(user)
        else:
            send_whatsapp_message(phone, "Hmm, não consegui confirmar o pagamento para o nome correto. Tente enviar uma imagem mais nítida do comprovante. Se o problema persistir, fale com o suporte.")
    else:
        send_whatsapp_message(phone, "Ainda não recebi a imagem. É só me enviar a foto do comprovante de pagamento.")

def deliver_final_product(user, test_data=None, debug=False):
    phone, plan = user['phone'], user.get('plan')
    resume_data = test_data if test_data else json.loads(user.get('resume_data', '{}'))
    
    if debug:
        templates_to_test = ['moderno', 'classico', 'criativo']
        for t in templates_to_test:
            send_whatsapp_message(phone, f"Gerando currículo de teste: *{t.capitalize()}*...")
            pdf_path = os.path.join(TEMP_DIR, f"Curriculo_{t}.pdf")
            generate_resume_pdf(resume_data, t, pdf_path)
            send_whatsapp_document(phone, pdf_path, os.path.basename(pdf_path), f"Modelo: {t.capitalize()}")
            os.remove(pdf_path)
            
            english_data = translate_resume_data_to_english(resume_data)
            if english_data:
                english_pdf_path = os.path.join(TEMP_DIR, f"Resume_English_{t}.pdf")
                generate_resume_pdf(english_data, t, english_pdf_path)
                send_whatsapp_document(phone, english_pdf_path, os.path.basename(english_pdf_path), f"Modelo Inglês: {t.capitalize()}")
                os.remove(english_pdf_path)

        send_whatsapp_message(phone, "Gerando carta de apresentação de teste...")
        cover_letter_text = generate_cover_letter_text(resume_data)
        if cover_letter_text:
            letter_path = os.path.join(TEMP_DIR, f"carta_apresentacao_{phone}.pdf")
            generate_simple_text_pdf(cover_letter_text, letter_path)
            send_whatsapp_document(phone, letter_path, "Carta_de_Apresentacao.pdf", "E aqui sua carta de apresentação!")
            os.remove(letter_path)
        send_whatsapp_message(phone, "Modo de teste concluído!")
        update_user(phone, {'state': 'completed'}) # Finaliza o fluxo de teste
        return

    template = user['template']
    send_whatsapp_message(phone, "Preparando seu currículo principal...")
    pdf_path = os.path.join(TEMP_DIR, f"Curriculo_{resume_data.get('nome_completo', 'user').split(' ')[0]}.pdf")
    generate_resume_pdf(resume_data, template, pdf_path)
    send_whatsapp_document(phone, pdf_path, os.path.basename(pdf_path), "Seu currículo novinho em folha!")
    os.remove(pdf_path)
    
    if plan in ['premium', 'revisao_humana']:
        send_whatsapp_message(phone, "Gerando bônus do plano premium...")
        english_data = translate_resume_data_to_english(resume_data)
        if english_data:
            english_pdf_path = os.path.join(TEMP_DIR, f"Resume_English_{english_data.get('full_name', 'user').split(' ')[0]}.pdf")
            generate_resume_pdf(english_data, template, english_pdf_path)
            send_whatsapp_document(phone, english_pdf_path, os.path.basename(english_pdf_path), "Aqui está sua versão em Inglês!")
            os.remove(english_pdf_path)
        cover_letter_text = generate_cover_letter_text(resume_data)
        if cover_letter_text:
            letter_path = os.path.join(TEMP_DIR, f"carta_apresentacao_{phone}.pdf")
            generate_simple_text_pdf(cover_letter_text, letter_path)
            send_whatsapp_document(phone, letter_path, "Carta_de_Apresentacao.pdf", "E aqui sua carta de apresentação!")
            os.remove(letter_path)
            
    if plan == 'revisao_humana':
        send_whatsapp_message(phone, "Sua solicitação de revisão foi enviada para nossa equipe! Em até 24h úteis um especialista entrará em contato. 👨‍💼")
    
    update_user(phone, {'state': 'awaiting_interview_prep_choice'})
    send_whatsapp_message(phone, "Seus arquivos foram entregues! 📄✨\n\nComo um bônus final, gostaria que eu gerasse uma lista de possíveis perguntas de entrevista com base no seu currículo? (Responda com *sim* ou *não*)")

@handle_state('awaiting_interview_prep_choice')
def handle_interview_prep(user, message_data):
    phone = user['phone']
    choice = message_data.get('text', '').lower().strip()
    if choice == 'sim':
        send_whatsapp_message(phone, "Ótima ideia! Analisando seu perfil para criar as melhores perguntas... 🧠")
        resume_data = json.loads(user['resume_data'])
        questions = generate_interview_questions(resume_data)
        send_whatsapp_message(phone, f"Aqui estão algumas perguntas para você treinar:\n\n{questions}")
        send_whatsapp_message(phone, "Boa sorte na sua preparação! 🚀")
    else:
        send_whatsapp_message(phone, "Entendido! Sem problemas. Muito sucesso na sua jornada! 🚀")
    update_user(phone, {'state': 'completed'})
    
@handle_state('completed')
def handle_completed(user, message_data):
    send_whatsapp_message(user['phone'], f"Olá! Eu sou o {BOT_NAME}. Já finalizamos seu currículo, mas se precisar de uma nova versão ou de ajuda com outra coisa, é só me chamar digitando 'oi' para recomeçar! 😉")

def handle_default(user, message_data):
    phone = user['phone']
    text = message_data.get('text', '').lower().strip()
    # Palavra-chave para reiniciar o fluxo
    if text in ['oi', 'ola', 'olá', 'recomeçar', 'começar']:
        update_user(phone, {'state': 'awaiting_welcome', 'resume_data': json.dumps({}), 'plan': 'none', 'template': 'none', 'payment_verified': 0})
        handle_welcome(user, message_data)
    else:
        send_whatsapp_message(user['phone'], "Desculpe, não entendi o que você quis dizer. Para recomeçar o processo de criação do currículo, digite 'oi'.")


# ==============================================================================
# --- WEBHOOK e INICIALIZAÇÃO
# ==============================================================================
@app.route('/')
def health_check():
    return "Cadu está no ar!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"Webhook recebido: {json.dumps(data, indent=2)}")
        
        # Adaptação para diferentes estruturas de webhook da Z-API
        phone = data.get('phone')
        message_data = {}
        
        # Mensagem de texto
        if data.get('text') and isinstance(data.get('text'), str): # Estrutura mais nova/simples
            message_data['text'] = data['text']
        elif data.get('text') and isinstance(data.get('text'), dict) and 'message' in data['text']: # Estrutura antiga
            message_data['text'] = data['text']['message']
        
        # Mensagem de imagem
        elif data.get('type') == 'image' and data.get('imageUrl'):
            message_data['image'] = {'url': data['imageUrl']}
        elif data.get('image') and isinstance(data.get('image'), dict) and 'imageUrl' in data['image']:
             message_data['image'] = {'url': data['image']['imageUrl']}

        if phone and message_data:
            process_message(phone, message_data)
        else:
            logging.warning(f"Webhook de {phone} recebido sem dados de mensagem válidos ou número de telefone.")
            
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
        
        # Adiciona condição para não lembrar usuários que já receberam lembrete
        cursor.execute("SELECT * FROM users WHERE last_interaction < ? AND state NOT IN ('completed', 'reminded', 'delivering')", (time_limit,))
        abandoned_users = cursor.fetchall()
        
        for user in abandoned_users:
            logging.info(f"Enviando lembrete para: {user['phone']}")
            message = f"Olá, {BOT_NAME} passando para dar um oi! 👋 Vi que começamos a montar seu currículo mas não terminamos. Que tal continuarmos de onde paramos? É só responder a última pergunta!"
            send_whatsapp_message(user['phone'], message)
            update_user(user['phone'], {'state': 'reminded'}) # Atualiza o estado para não enviar novamente
            
        conn.close()

init_database()

if __name__ == '__main__':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_abandoned_sessions, 'interval', hours=6)
    scheduler.start()
    port = int(os.environ.get('PORT', 8080))
    # 'debug=False' é importante para produção
    app.run(host='0.0.0.0', port=port, debug=False)
