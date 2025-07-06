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
    gemini_vision_model = genai.GenerativeModel('gemini-1.5-vision-pro') # Modelo para analisar imagens
    logging.info("API do Google Gemini configurada com sucesso.")
except Exception as e:
    logging.error(f"Falha ao configurar a API do Google: {e}")
    gemini_model = None
    gemini_vision_model = None

# --- CONFIGURAÇÕES DE PAGAMENTO ---
PIX_RECIPIENT_NAME = "Leonardo Maciel Abbadi"
PIX_CITY = "Brasilia"
# Chave PIX fornecida
PIX_KEY = "00020126580014br.gov.bcb.pix0136fd3412eb-9577-41ea-ba4d-12293570c0155204000053039865802BR5922Leonardo Maciel Abbadi6008Brasilia62240520daqr1894289448628220630439D1"
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
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # Tabela mais robusta para suportar as novas funcionalidades
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

# Funções auxiliares do banco de dados
def get_user(phone):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(phone, data):
    # Função unificada para atualizar qualquer dado do usuário
    user = get_user(phone)
    if not user:
        # Cria um novo usuário se não existir
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Garante que todos os campos sejam inicializados
        initial_data = {
            'phone': phone,
            'state': 'awaiting_welcome',
            'resume_data': json.dumps({}),
            'plan': 'none',
            'template': 'none',
            'payment_verified': 0,
            'last_interaction': datetime.now()
        }
        initial_data.update(data)
        columns = ', '.join(initial_data.keys())
        placeholders = ', '.join('?' * len(initial_data))
        sql = f'INSERT INTO users ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, tuple(initial_data.values()))
        conn.commit()
        conn.close()
    else:
        # Atualiza um usuário existente
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        # Sempre atualiza o timestamp da última interação
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
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao enviar mensagem para {phone}: {e}")

def send_whatsapp_document(phone, doc_path, filename, caption=""):
    logging.info(f"Enviando documento {filename} para {phone}")
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(doc_path, 'rb') as f:
        doc_bytes = f.read()
    doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
    payload = {
        "phone": phone,
        "document": f"data:application/pdf;base64,{doc_base64}",
        "fileName": filename,
        "caption": caption
    }
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
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
    prompt = f"""
    Analise a conversa a seguir.
    A pergunta feita foi: "{question}"
    A resposta do usuário foi: "{user_message}"

    Extraia APENAS a informação principal da resposta do usuário, sem a fraseologia extra.
    Por exemplo, se a pergunta é "Qual seu nome completo?" e a resposta é "o meu nome completo é joão da silva", extraia apenas "joão da silva".
    Se a pergunta é "Qual sua idade?" e a resposta é "tenho 25 anos", extraia apenas "25".
    Se a resposta for "não quero informar", extraia "Não informado".

    Informação extraída:
    """
    return get_ia_response(prompt)

def improve_text_with_ia(text_to_improve):
    prompt = f"""
    Corrija e melhore o texto a seguir para um currículo profissional.
    Corrija erros de português, gramática e ajuste o uso de letras maiúsculas/minúsculas.
    Mantenha o sentido original, mas torne a escrita mais impactante e clara.
    Texto original: "{text_to_improve}"

    Texto corrigido e melhorado:
    """
    return get_ia_response(prompt)

def analyze_pix_receipt(image_url):
    if not gemini_vision_model: return {'verified': False, 'reason': 'IA de visão indisponível.'}
    try:
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        image_data = image_response.content

        prompt = f"""
        Analise a imagem deste comprovante de PIX. Verifique as seguintes informações:
        1. O nome do recebedor é "{PIX_RECIPIENT_NAME}"?
        2. A instituição de destino é "Mercado Pago" ou "MercadoPago"?

        Responda APENAS com um objeto JSON com as chaves "verified" (true/false) e "reason" (uma breve explicação em português).
        Exemplo de resposta válida: {{"verified": true, "reason": "Nome e instituição confirmados."}}
        Exemplo de resposta inválida: {{"verified": false, "reason": "O nome do recebedor está incorreto."}}
        """
        response = gemini_vision_model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': image_data}])
        
        # Limpeza da resposta da IA para garantir que seja um JSON válido
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)

    except Exception as e:
        logging.error(f"Erro ao analisar comprovante PIX: {e}")
        return {'verified': False, 'reason': 'Não consegui ler a imagem do comprovante.'}

# ==============================================================================
# --- GERAÇÃO DE PDF (5 TEMPLATES)
# ==============================================================================
# (FPDF não suporta emojis, então eles são removidos antes de gerar)
def clean_text_for_pdf(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_resume_pdf(data, template_choice):
    # Roteador para a função de template correta
    templates = {
        'classico': generate_template_classico,
        'moderno': generate_template_moderno,
        'criativo': generate_template_criativo,
        'minimalista': generate_template_minimalista,
        'tecnico': generate_template_tecnico
    }
    
    pdf_function = templates.get(template_choice, generate_template_classico)
    clean_data = {k: clean_text_for_pdf(str(v)) for k, v in data.items()}
    
    path = os.path.join(TEMP_DIR, f"curriculo_{data.get('phone', 'user')}.pdf")
    pdf_function(clean_data, path)
    return path

# --- TEMPLATE 1: CLÁSSICO ---
def generate_template_classico(data, path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, data.get('nome_completo', ''), 0, 1, 'C')
    pdf.set_font("Arial", '', 10)
    contato = f"{data.get('cidade_estado', '')} | {data.get('telefone', '')} | {data.get('email', '')}"
    pdf.cell(0, 10, contato, 0, 1, 'C')
    pdf.ln(10)

    # Função para adicionar seções
    def add_section(title, content):
        if content and content != '[]':
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, title, 0, 1, 'L')
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Arial", '', 10)
            pdf.multi_cell(0, 5, str(content).replace("['", "- ").replace("']", "").replace("', '", "\n- "))
            pdf.ln(5)

    add_section("CARGO DESEJADO", data.get('cargo'))
    add_section("RESUMO PROFISSIONAL", data.get('resumo'))
    add_section("EXPERIÊNCIA PROFISSIONAL", data.get('experiencias'))
    add_section("FORMAÇÃO ACADÊMICA", data.get('formacao'))
    add_section("HABILIDADES E COMPETÊNCIAS", data.get('habilidades'))
    add_section("CURSOS EXTRAS", data.get('cursos'))

    pdf.output(path)

# (Os outros 4 templates seguiriam uma estrutura similar, mudando fontes, layout, cores, etc.)
# --- Adicionando placeholders para os outros templates para o código funcionar ---
def generate_template_moderno(data, path):
    # Lógica para um template moderno (ex: com uma barra lateral)
    generate_template_classico(data, path) # Placeholder

def generate_template_criativo(data, path):
    # Lógica para um template criativo (ex: com ícones e cores)
    generate_template_classico(data, path) # Placeholder

def generate_template_minimalista(data, path):
    # Lógica para um template minimalista (ex: muito espaço em branco, fontes limpas)
    generate_template_classico(data, path) # Placeholder

def generate_template_tecnico(data, path):
    # Lógica para um template técnico (ex: focado em habilidades e certificações)
    generate_template_classico(data, path) # Placeholder

# ==============================================================================
# --- FLUXO DA CONVERSA (STATE MACHINE)
# ==============================================================================
# Define o fluxo de perguntas
CONVERSATION_FLOW = [
    ('nome_completo', 'Legal! Para começar, qual o seu nome completo?'),
    ('cidade_estado', 'Ótimo, {nome}! Agora me diga em qual cidade e estado você mora.'),
    ('telefone', 'Pode me informar um telefone de contato com DDD?'),
    ('email', 'Qual o seu melhor e-mail para contato?'),
    ('cargo', 'Certo. Qual o cargo ou área que você está buscando? (Ex: Vendedor, Desenvolvedor, Administrativo)'),
    ('resumo', 'Vamos caprichar! Escreva um pequeno resumo sobre você e seus objetivos profissionais. (Se não tiver, diga "pular" e eu crio um pra você depois).'),
    ('experiencias', 'Agora, me conte sobre suas experiências profissionais. Pode enviar uma de cada vez, e quando terminar, digite "pronto".'),
    ('formacao', 'Qual a sua formação? (Ex: Ensino Médio Completo, Graduação em Administração na USP)'),
    ('habilidades', 'Quais são suas principais habilidades? (Ex: Pacote Office, Comunicação, Liderança). Pode listar várias, separando por vírgula.'),
    ('cursos', 'Você tem cursos ou certificações importantes? Se sim, me conte um por um. Quando acabar, é só dizer "pronto".')
]

# Mapeamento de estados para funções de processamento
state_handlers = {}

def handle_state(state):
    def decorator(func):
        state_handlers[state] = func
        return func
    return decorator

def process_message(phone, message_data):
    user = get_user(phone)
    if not user:
        # Primeiro contato do usuário
        update_user(phone, {'state': 'awaiting_welcome'})
        user = get_user(phone)
    
    state = user['state']
    handler = state_handlers.get(state, handle_default)
    handler(user, message_data)

# --- HANDLERS DE ESTADO ---

@handle_state('awaiting_welcome')
def handle_welcome(user, message_data):
    phone = user['phone']
    send_whatsapp_message(phone, f"Olá! Eu sou o {BOT_NAME} 🤖, seu novo assistente de carreira. Vou te ajudar a criar um currículo profissional incrível!")
    send_whatsapp_message(phone, "Para começarmos, eu tenho 5 estilos de currículo. Escolha o que mais combina com você:\n\n1. *Clássico:* Tradicional e direto.\n2. *Moderno:* Com um design mais arrojado.\n3. *Criativo:* Para áreas de design e marketing.\n4. *Minimalista:* Limpo e focado no essencial.\n5. *Técnico:* Ideal para áreas de TI e engenharia.\n\nÉ só me dizer o número ou o nome do seu preferido!")
    update_user(phone, {'state': 'choosing_template'})

@handle_state('choosing_template')
def handle_choosing_template(user, message_data):
    phone = user['phone']
    message = message_data.get('text', '').lower()
    template_map = {'1': 'classico', 'clássico': 'classico', 'classico': 'classico',
                    '2': 'moderno', 'moderno': 'moderno',
                    '3': 'criativo', 'criativo': 'criativo',
                    '4': 'minimalista', 'minimalista': 'minimalista',
                    '5': 'tecnico', 'técnico': 'tecnico', 'tecnico': 'tecnico'}
    
    chosen_template = template_map.get(message)
    if chosen_template:
        update_user(phone, {'template': chosen_template, 'state': 'flow_nome_completo'})
        send_whatsapp_message(phone, f"Ótima escolha! Vamos criar seu currículo no estilo *{chosen_template.capitalize()}*.")
        send_whatsapp_message(phone, CONVERSATION_FLOW[0][1])
    else:
        send_whatsapp_message(phone, "Não entendi sua escolha. Por favor, me diga o nome ou o número do template (de 1 a 5).")

# ... Geradores dinâmicos para o fluxo principal ...
def create_flow_handler(current_step_index):
    current_key, current_question = CONVERSATION_FLOW[current_step_index]
    
    @handle_state(f'flow_{current_key}')
    def flow_handler(user, message_data):
        phone = user['phone']
        message = message_data.get('text', '')
        resume_data = json.loads(user['resume_data'])
        
        # Lógica especial para campos de lista (experiências, cursos)
        is_list_field = current_key in ['experiencias', 'cursos']
        if is_list_field and message.lower().strip() in ['pronto', 'ok', 'finalizar']:
            go_to_next_step(phone, resume_data, current_step_index)
            return

        # Extração de informação com IA
        extracted_info = extract_info_from_message(current_question, message)
        
        if is_list_field:
            if current_key not in resume_data: resume_data[current_key] = []
            resume_data[current_key].append(extracted_info)
            send_whatsapp_message(phone, f"Legal, adicionei! Pode me mandar o próximo ou digitar *'pronto'* para continuar.")
        else:
            resume_data[current_key] = extracted_info
            go_to_next_step(phone, resume_data, current_step_index)

        # Salva o progresso
        update_user(phone, {'resume_data': json.dumps(resume_data)})

    def go_to_next_step(phone, resume_data, current_idx):
        if current_idx + 1 < len(CONVERSATION_FLOW):
            next_key, next_question = CONVERSATION_FLOW[current_idx + 1]
            # Personaliza a próxima pergunta com o nome do usuário
            if '{nome}' in next_question:
                user_name = resume_data.get('nome_completo', '').split(' ')[0]
                next_question = next_question.format(nome=user_name)

            send_whatsapp_message(phone, next_question)
            update_user(phone, {'state': f'flow_{next_key}'})
        else:
            # Fim do fluxo de coleta de dados
            send_whatsapp_message(phone, "Ufa! Terminamos a coleta de dados. 💪")
            show_review_menu(phone, resume_data)

# Registra todos os handlers do fluxo principal
for i in range(len(CONVERSATION_FLOW)):
    create_flow_handler(i)

# --- Menu de Edição e Pagamento ---
def show_review_menu(phone, resume_data):
    review_text = "Antes de finalizar, vamos revisar tudo. Se algo estiver errado, é só me dizer o número do item que quer corrigir:\n\n"
    for i, (key, _) in enumerate(CONVERSATION_FLOW):
        review_text += f"*{i+1}. {key.replace('_', ' ').capitalize()}:* {resume_data.get(key, 'Não preenchido')}\n"
    review_text += "\nSe estiver tudo certo, digite *'pagar'* para irmos para o pagamento!"
    
    send_whatsapp_message(phone, review_text)
    update_user(phone, {'state': 'awaiting_review_choice'})

@handle_state('awaiting_review_choice')
def handle_review_choice(user, message_data):
    phone = user['phone']
    message = message_data.get('text', '').lower().strip()

    if message in ['pagar', 'tudo certo', 'ok']:
        show_payment_options(phone)
        return
    
    try:
        choice = int(message)
        if 1 <= choice <= len(CONVERSATION_FLOW):
            key_to_edit, question_to_ask = CONVERSATION_FLOW[choice-1]
            update_user(phone, {'state': f'editing_{key_to_edit}'})
            send_whatsapp_message(phone, f"Ok, vamos corrigir *{key_to_edit.replace('_', ' ')}*. Por favor, me envie a informação correta.")
        else:
            raise ValueError()
    except (ValueError, IndexError):
        send_whatsapp_message(phone, "Não entendi. Por favor, digite o *número* do item para editar ou *'pagar'* para continuar.")

# ... Geradores dinâmicos para a edição ...
def create_editing_handler(edit_step_index):
    key_to_edit, _ = CONVERSATION_FLOW[edit_step_index]

    @handle_state(f'editing_{key_to_edit}')
    def editing_handler(user, message_data):
        phone = user['phone']
        message = message_data.get('text', '')
        resume_data = json.loads(user['resume_data'])
        
        # Extração de informação com IA
        extracted_info = extract_info_from_message(f"Qual o novo valor para {key_to_edit}?", message)
        resume_data[key_to_edit] = extracted_info
        
        update_user(phone, {'resume_data': json.dumps(resume_data)})
        send_whatsapp_message(phone, "Corrigido! 👍")
        show_review_menu(phone, resume_data) # Volta para o menu de revisão

for i in range(len(CONVERSATION_FLOW)):
    create_editing_handler(i)


def show_payment_options(phone):
    message = f"""
Prontinho! Seu currículo está pronto para ser gerado. Escolha seu plano:

📄 *PLANO BÁSICO - R$ {PRECO_BASICO:.2f}*
- Currículo em PDF no template que você escolheu.

✨ *PLANO PREMIUM - R$ {PRECO_PREMIUM:.2f}*
- Tudo do Básico, e mais:
- Versão do currículo em Inglês.
- Carta de apresentação profissional em PDF.

👨‍💼 *REVISÃO HUMANA - R$ {PRECO_REVISAO_HUMANA:.2f}*
- Tudo do Premium, e mais:
- Um especialista de RH vai revisar seu currículo e te dar dicas valiosas.

Digite *básico*, *premium* ou *revisão* para escolher.
    """
    send_whatsapp_message(phone, message)
    update_user(phone, {'state': 'awaiting_plan_choice'})

@handle_state('awaiting_plan_choice')
def handle_plan_choice(user, message_data):
    phone = user['phone']
    choice = message_data.get('text', '').lower().strip()
    
    plans = {
        'básico': ('basico', PRECO_BASICO),
        'premium': ('premium', PRECO_PREMIUM),
        'revisão': ('revisao_humana', PRECO_REVISAO_HUMANA)
    }

    if choice in plans:
        plan_name, price = plans[choice]
        update_user(phone, {'plan': plan_name})
        
        # Gera o código PIX dinamicamente (apesar da chave ser completa, a boa prática é usar a lib)
        pix = Pix(pix_key=PIX_KEY, merchant_name=PIX_RECIPIENT_NAME, merchant_city=PIX_CITY, amount=price)
        pix_code = pix.get_br_code()

        send_whatsapp_message(phone, f"Ótimo! O valor para o plano *{plan_name.replace('_', ' ').capitalize()}* é R$ {price:.2f}.")
        send_whatsapp_message(phone, "Você pode pagar usando o código PIX Copia e Cola abaixo:")
        send_whatsapp_message(phone, pix_code)
        send_whatsapp_message(phone, "Depois de pagar, é só me enviar uma *foto do comprovante* que eu libero seu currículo na hora! ✨")
        update_user(phone, {'state': 'awaiting_payment_proof'})
    else:
        send_whatsapp_message(phone, "Plano não reconhecido. Por favor, escolha entre *básico*, *premium* ou *revisão*.")


@handle_state('awaiting_payment_proof')
def handle_payment_proof(user, message_data):
    phone = user['phone']
    
    if 'image' in message_data:
        image_url = message_data['image']['url']
        send_whatsapp_message(phone, "Oba, recebi seu comprovante! 🕵️‍♂️ Vou pedir pra minha IA dar uma olhadinha, só um segundo...")

        analysis = analyze_pix_receipt(image_url)
        
        if analysis.get('verified'):
            send_whatsapp_message(phone, f"Pagamento confirmado! ✅\nMotivo: {analysis.get('reason')}")
            send_whatsapp_message(phone, "Estou preparando seus arquivos, um momento...")
            update_user(phone, {'payment_verified': 1})
            deliver_final_product(user)
        else:
            send_whatsapp_message(phone, f"Hmm, não consegui confirmar seu pagamento. 😕\nMotivo: {analysis.get('reason')}")
            send_whatsapp_message(phone, "Pode tentar enviar uma imagem mais nítida, por favor?")
    else:
        send_whatsapp_message(phone, "Ainda não recebi a imagem do seu comprovante. É só me enviar a foto que eu analiso aqui!")

def deliver_final_product(user):
    phone = user['phone']
    plan = user['plan']
    template = user['template']
    resume_data = json.loads(user['resume_data'])

    # Gera e envia o currículo principal
    pdf_path = generate_resume_pdf(resume_data, template)
    send_whatsapp_document(phone, pdf_path, f"Curriculo_{resume_data.get('nome_completo')}.pdf", "Seu currículo novinho em folha!")
    os.remove(pdf_path)

    if plan in ['premium', 'revisao_humana']:
        # Simula a geração dos outros itens
        send_whatsapp_message(phone, "Gerando seus bônus do plano premium...")
        # Lógica para gerar versão em inglês e carta de apresentação
        send_whatsapp_message(phone, "[Arquivo Simulado] Curriculo_em_Ingles.pdf")
        send_whatsapp_message(phone, "[Arquivo Simulado] Carta_de_Apresentacao.pdf")

    if plan == 'revisao_humana':
        send_whatsapp_message(phone, "Sua solicitação de revisão foi enviada para nossa equipe de especialistas! Em até 24 horas úteis, um de nossos consultores entrará em contato com o feedback. 👨‍💼")

    send_whatsapp_message(phone, f"Prontinho! Muito obrigado por usar o {BOT_NAME}. Desejo muito sucesso na sua busca por um novo desafio! 🚀")
    update_user(phone, {'state': 'completed'})

@handle_state('completed')
def handle_completed(user, message_data):
    send_whatsapp_message(user['phone'], f"Olá! Vi que você já completou seu currículo. Se precisar de uma nova versão ou quiser conhecer nossos outros serviços, é só me chamar!")

def handle_default(user, message_data):
    send_whatsapp_message(user['phone'], "Desculpe, não entendi o que você quis dizer. Se quiser recomeçar, digite 'oi'.")


# ==============================================================================
# --- WEBHOOK (PONTO DE ENTRADA DAS MENSAGENS)
# ==============================================================================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        logging.info(f"Webhook recebido: {json.dumps(data, indent=2)}")

        # Adaptação para diferentes formatos de webhook (Z-API)
        phone = data.get('phone')
        message_data = {}
        if 'text' in data:
            message_data['text'] = data['text']
        if 'message' in data and 'image' in data['message']:
             # Assume que o webhook da Z-API para imagem tem essa estrutura
            message_data['image'] = {'url': data['message']['image']['url']}

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
        logging.info("Executando tarefa agendada: Verificando sessões abandonadas...")
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Pega usuários que não interagem há mais de 24h e não completaram o processo
        time_limit = datetime.now() - timedelta(hours=24)
        cursor.execute("SELECT * FROM users WHERE last_interaction < ? AND state != 'completed'", (time_limit,))
        abandoned_users = cursor.fetchall()
        
        for user in abandoned_users:
            logging.info(f"Enviando lembrete para o usuário abandonado: {user['phone']}")
            message = f"Olá, {BOT_NAME} passando para dar um oi! 👋 Vi que começamos a montar seu currículo mas não terminamos. Que tal continuarmos de onde paramos? É só me responder aqui que a gente retoma!"
            send_whatsapp_message(user['phone'], message)
            # Atualiza o estado para não enviar de novo
            update_user(user['phone'], {'state': 'reminded'}) # Um novo estado para controlar o lembrete

        conn.close()

# ==============================================================================
# --- INICIALIZAÇÃO DO SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    init_database()
    
    # Inicializa o agendador de tarefas em background
    scheduler = BackgroundScheduler(daemon=True)
    # Roda a verificação a cada 6 horas
    scheduler.add_job(check_abandoned_sessions, 'interval', hours=6)
    scheduler.start()
    
    # Pega a porta do ambiente, padrão para 8080 se não definida
    port = int(os.environ.get('PORT', 8080))
    # Para deploy, o debug deve ser False
    app.run(host='0.0.0.0', port=port, debug=False)
