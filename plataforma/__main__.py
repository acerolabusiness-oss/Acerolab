"""Sobe a plataforma.

    .venv/bin/python -m plataforma            # 127.0.0.1:8000
    .venv/bin/python -m plataforma --porta 9000 --publico
"""
from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> int:
    p = argparse.ArgumentParser(prog="plataforma")
    p.add_argument("--porta", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--publico", action="store_true",
                   help="escuta em 0.0.0.0 em vez de só no próprio Mac")
    p.add_argument("--recarregar", action="store_true", help="recarrega ao salvar arquivo")
    args = p.parse_args()

    uvicorn.run("plataforma.app:app",
                host="0.0.0.0" if args.publico or os.environ.get("RAILWAY_ENVIRONMENT") else "127.0.0.1",
                port=args.porta, reload=args.recarregar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
