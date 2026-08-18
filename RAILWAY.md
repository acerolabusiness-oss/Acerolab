# Deploy no Railway

## Setup rápido

1. **Crie um projeto no Railway:** https://railway.app
2. **Conecte o repositório GitHub**
3. **Railway detectará o `Dockerfile` automaticamente**
4. **Configure as variáveis de ambiente:**

```bash
ANTHROPIC_API_KEY=sua_chave_anthropic
FAL_KEY=sua_chave_fal
ELEVENLABS_API_KEY=sua_chave_elevenlabs
GROQ_API_KEY=sua_chave_groq
SUPABASE_URL=sua_url_supabase
SUPABASE_ANON_KEY=sua_chave_supabase_anon
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
PUBLIC_URL=https://seu-projeto.up.railway.app
# caminho do volume persistente montado no Railway
ACEROLAB_DATA_DIR=/data
DOLAR=5.00
```

5. **Confirme o deploy** — Railway faz build automático
6. **A plataforma estará em:** `https://seu-projeto-railway.up.railway.app`

## Banco de dados

O banco e os MP4 ficam em `ACEROLAB_DATA_DIR`. Monte um volume persistente do
Railway em `/data`; sem volume, cada restart perde banco e vídeos.

Para manter dados entre deploys, configure uma postgres no Railway:
- Adicione "PostgreSQL" no Railway
- Mude o `plataforma/banco.py` para usar PostgreSQL em vez de SQLite
- Configure a env var `DATABASE_URL`

SQLite com volume serve para uma instância de MVP. Antes de escalar para mais
de uma réplica, migre a fila e o banco para Postgres e os MP4 para object storage.

## Landing page

A landing estática (`site/landing.html`) fica em outro lugar:
- **Netlify:** arraste o arquivo `site/` para Netlify (grátis)
- **Vercel:** mesmo processo
- Link a landing para a plataforma em Railway via `PLATAFORMA_URL`

## Logs

Railway mostra logs em tempo real no painel. Para erros, confira:
- `Railway Dashboard → Logs`
- Variáveis de ambiente faltando
- Porta não respondendo
