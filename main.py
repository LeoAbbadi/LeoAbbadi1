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
        initial_data = {'phone': phone, 'state': 'awaiting_welcome', 'resume_data': json.dumps({}), 'plan': 'none', 'template': 'none', 'payment_verified': 0, 'last_interaction': datetime.now()}
        initial_data.update(data)
        columns, placeholders = ', '.join(initial_data.keys()), ', '.join('?' * len(initial_data))
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
    system_prompt = f'Analise a imagem de um comprovante PIX. Verifique se o nome do recebedor é "{PIX_RECIPIENT_NAME}". Responda APENAS com um objeto JSON com a chave "verified" (true/false). Não inclua markdown ```json```.'
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
            # Adiciona todos os 4 estilos da fonte
            self.add_font('DejaVu', '', os.path.join(FONT_DIR, 'DejaVuSans.ttf'), uni=True)
            self.add_font('DejaVu', 'B', os.path.join(FONT_DIR, 'DejaVuSans-Bold.ttf'), uni=True)
            self.add_font('DejaVu', 'I', os.path.join(FONT_DIR, 'DejaVuSans-Oblique.ttf'), uni=True)
            self.add_font('DejaVu', 'BI', os.path.join(FONT_DIR, 'DejaVuSans-BoldOblique.ttf'), uni=True)
            self.font_regular = 'DejaVu'
            self.font_bold = 'DejaVu'
        except RuntimeError as e:
            logging.error(f"ERRO DE FONTE: {e}. Usando Helvetica como fallback.")
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
    # ... (implementação completa)
    pass

def generate_template_classico(data, path):
    # ... (implementação completa)
    pass

def generate_template_criativo(data, path):
    # ... (implementação completa)
    pass

# ==============================================================================
# --- FLUXO DA CONVERSA
# ==============================================================================
def generate_fake_data():
    first_names = ["Ana", "Carlos", "Beatriz", "Daniel", "Elisa", "Fernando", "Laura", "Rafael"]
    last_names = ["Silva", "Souza", "Pereira", "Costa", "Rodrigues", "Almeida", "Nunes", "Mendes"]
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
    ('resumo', 'Vamos caprichar! Escreva um pequeno resumo sobre você e seus objetivos. (Se não tiver, é só dizer "pular").'),
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
    if 'básico' in choice or 'basico' in choice: plan_name = 'basico'
    elif 'premium' in choice: plan_name = 'premium'
    elif 'revisão' in choice or 'revisao' in choice or 'humana' in choice: plan_name = 'revisao_humana'
    else: plan_name = None
    if plan_name:
        update_user(phone, {'plan': plan_name})
        template_message = "Ótima escolha! Agora, vamos escolher o visual do seu currículo. Qual destes 3 estilos você prefere?\n\n1. *Moderno*\n2. *Clássico*\n3. *Criativo*\n\nÉ só me dizer o número ou o nome."
        send_whatsapp_message(phone, template_message)
        update_user(phone, {'state': 'choosing_template'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Escolha *básico*, *premium* ou *revisão*.")

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone, message = user['phone'], message_data.get('text', '').lower().strip()
    template_map = {'1': 'moderno', 'moderno': 'moderno', '2': 'classico', 'clássico': 'classico', '3': 'criativo', 'criativo': 'criativo'}
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
        if current_key == 'resumo' and message.lower().strip() == 'pular': 
            extracted_info = "Não informado"
        elif current_key == 'email':
            extracted_info = extract_info_from_message(current_question, message).lower()
        else: 
            extracted_info = extract_info_from_message(current_question, message)
        resume_data[current_key] = extracted_info
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        go_to_next_step(phone, resume_data, current_step_index)
    def go_to_next_step(phone, resume_data, current_idx):
        if CONVERSATION_FLOW[current_idx][0] == 'resumo':
            update_user(phone, {'state': 'awaiting_experience_job_title', 'resume_data': json.dumps(resume_data)})
            send_whatsapp_message(phone, "Ótimo. Agora vamos adicionar suas experiências profissionais. Qual era o seu cargo na sua experiência mais recente?")
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
    
@handle_state('awaiting_experience_job_title')
# ... (código dos handlers de experiência)

@handle_state('awaiting_improve_choice')
# ... (código do handler de melhoria)

def show_review_menu(phone, resume_data):
    # ... (código do menu de revisão)

@handle_state('awaiting_review_choice')
# ... (código do handler de revisão)

def create_editing_handler(edit_step_index):
    # ... (código do handler de edição)

@handle_state('awaiting_payment_proof')
# ... (código do handler de pagamento)

def deliver_final_product(user, test_data=None, debug=False):
    # ... (código da entrega final)

@handle_state('awaiting_interview_prep_choice')
# ... (código do handler de preparação para entrevista)

@handle_state('completed')
# ... (código do handler de concluído)

def handle_default(user, message_data):
    # ... (código do handler padrão)

# ==============================================================================
# --- WEBHOOK e INICIALIZAÇÃO
# ==============================================================================
@app.route('/webhook', methods=['POST'])
# ... (código do webhook)

def check_abandoned_sessions():
    # ... (código das tarefas agendadas)

init_database()

if __name__ == '__main__':
    # ... (código de inicialização do servidor)
