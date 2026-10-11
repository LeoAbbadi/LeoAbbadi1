-- Facilitador TikTok Shop: esquema inicial

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  name text NOT NULL DEFAULT '',
  password_hash text NOT NULL,
  -- free | starter | pro
  plan text NOT NULL DEFAULT 'free',
  -- monthly | annual
  plan_period text,
  -- active | past_due | canceled
  plan_status text NOT NULL DEFAULT 'active',
  plan_renews_at timestamptz,
  stripe_customer_id text,
  stripe_subscription_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  token_hash text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sessions_user_idx ON sessions(user_id);

-- Consumo mensal (zera a cada mês de calendário)
CREATE TABLE usage (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  period text NOT NULL, -- 'YYYY-MM'
  videos integer NOT NULL DEFAULT 0,
  scripts integer NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, period)
);

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  product_name text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX projects_user_idx ON projects(user_id, created_at DESC);

-- Pedaços gravados pelo usuário: ganchos, corpos e CTAs
CREATE TABLE clips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  slot text NOT NULL CHECK (slot IN ('hook', 'body', 'cta')),
  label text NOT NULL DEFAULT '',
  original_name text NOT NULL DEFAULT '',
  storage_key text NOT NULL,
  size_bytes bigint NOT NULL DEFAULT 0,
  -- uploading | ready
  status text NOT NULL DEFAULT 'uploading',
  -- versão padronizada (1080x1920, 30fps, áudio normalizado), feita uma única vez
  normalized_key text,
  duration_s real,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX clips_project_idx ON clips(project_id, slot, created_at);

-- Um lote = um pedido de "multiplicar". Também é a fila do worker.
CREATE TABLE batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- queued | processing | done | error | expired
  status text NOT NULL DEFAULT 'queued',
  total integer NOT NULL,
  done integer NOT NULL DEFAULT 0,
  posts_per_day integer NOT NULL DEFAULT 1,
  start_date date NOT NULL DEFAULT CURRENT_DATE,
  error text,
  zip_key text,
  zip_size_bytes bigint,
  attempts integer NOT NULL DEFAULT 0,
  locked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  expires_at timestamptz
);
CREATE INDEX batches_queue_idx ON batches(status, created_at);
CREATE INDEX batches_project_idx ON batches(project_id, created_at DESC);

-- Cada vídeo final do lote, já na ordem certa de postar
CREATE TABLE outputs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id uuid NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
  position integer NOT NULL,
  hook_clip_id uuid NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  body_clip_id uuid NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  cta_clip_id uuid NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  -- original | variacao | parecido
  label text NOT NULL,
  originality integer NOT NULL,
  suggested_date date NOT NULL,
  caption text NOT NULL DEFAULT '',
  storage_key text,
  size_bytes bigint,
  duration_s real,
  UNIQUE (batch_id, position)
);

-- Roteiros gerados com IA
CREATE TABLE scripts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- videos | live
  kind text NOT NULL,
  product_name text NOT NULL,
  input jsonb NOT NULL,
  output jsonb NOT NULL,
  model text NOT NULL,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX scripts_user_idx ON scripts(user_id, created_at DESC);

-- Catálogo de produtos do TikTok Shop (vem de um provedor de dados ou de importação CSV)
CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL DEFAULT 'csv',
  external_id text NOT NULL,
  country text NOT NULL DEFAULT 'BR',
  name text NOT NULL,
  category text NOT NULL DEFAULT '',
  shop_name text NOT NULL DEFAULT '',
  image_url text NOT NULL DEFAULT '',
  product_url text NOT NULL DEFAULT '',
  price_cents integer NOT NULL DEFAULT 0,
  commission_pct real NOT NULL DEFAULT 0,
  sales_1d integer NOT NULL DEFAULT 0,
  sales_7d integer NOT NULL DEFAULT 0,
  sales_30d integer NOT NULL DEFAULT 0,
  gmv_cents_1d bigint NOT NULL DEFAULT 0,
  gmv_cents_7d bigint NOT NULL DEFAULT 0,
  gmv_cents_30d bigint NOT NULL DEFAULT 0,
  -- crescimento das vendas nas últimas 24h em relação à média dos 7 dias
  growth_pct_1d real NOT NULL DEFAULT 0,
  creators_count integer NOT NULL DEFAULT 0,
  is_sample boolean NOT NULL DEFAULT false,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, external_id, country)
);
CREATE INDEX products_rank_idx ON products(country, gmv_cents_7d DESC);

CREATE TABLE product_videos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  creator_handle text NOT NULL,
  video_url text NOT NULL DEFAULT '',
  views bigint NOT NULL DEFAULT 0,
  gmv_cents bigint NOT NULL DEFAULT 0,
  posted_at date
);
CREATE INDEX product_videos_product_idx ON product_videos(product_id, views DESC);

CREATE TABLE favorites (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, product_id)
);
