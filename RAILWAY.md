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
DOLAR=5.00
```

5. **Confirme o deploy** — Railway faz build automático
6. **A plataforma estará em:** `https://seu-projeto-railway.up.railway.app`

## Banco de dados

O SQLite fica **local no container** do Railway. Cada restart cria um novo banco (dados são perdidos).

Para manter dados entre deploys, configure uma postgres no Railway:
- Adicione "PostgreSQL" no Railway
- Mude o `plataforma/banco.py` para usar PostgreSQL em vez de SQLite
- Configure a env var `DATABASE_URL`

Por enquanto, SQLite é ok para MVP.

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
