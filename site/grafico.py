"""Gera o gráfico de RPM em SVG puro — sem print de tela, sem dependência externa."""

# RPM diário do período, em dólar por mil visualizações
DIAS = [1.02, 1.05, 1.14, 1.28, 1.33, 1.09, 1.24, 0.95, 1.21, 1.49]
MEDIA = sum(DIAS) / len(DIAS)          # 1.180
TETO = 1.5
GRADE = [0, 0.5, 1.0, 1.5]

L, A = 520, 250                         # tela
ESQ, DIR, TOPO, BASE = 6, 46, 14, 34    # margens (rótulos do eixo ficam à direita)
PISO = A - BASE
ALTURA_UTIL = PISO - TOPO
LARG_UTIL = L - ESQ - DIR
PASSO = LARG_UTIL / len(DIAS)
BARRA = PASSO - 8                       # respiro de 8px entre barras
RAIO = 4                                # topo arredondado, conforme a especificação


def y_de(v):
    return PISO - (v / TETO) * ALTURA_UTIL


def barra(x, y, w, r=RAIO):
    """Retângulo com apenas o topo arredondado, preso à linha de base."""
    r = min(r, w / 2, PISO - y)
    return (f"M{x:.1f} {PISO:.1f}"
            f"L{x:.1f} {y + r:.1f}"
            f"Q{x:.1f} {y:.1f} {x + r:.1f} {y:.1f}"
            f"L{x + w - r:.1f} {y:.1f}"
            f"Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + r:.1f}"
            f"L{x + w:.1f} {PISO:.1f}Z")


def moeda(v):
    return f"US$ {v:.2f}".replace(".", ",")


def montar():
    p = []
    p.append(f'<svg class="g-rpm" viewBox="0 0 {L} {A}" role="img" '
             f'aria-label="RPM diário de 1 a 10 de fevereiro de 2026, média de {moeda(MEDIA)} por mil visualizações">')

    # grade + rótulos do eixo, ambos recessivos
    for g in GRADE:
        y = y_de(g)
        p.append(f'<line class="g-grade" x1="{ESQ}" y1="{y:.1f}" x2="{L - DIR + 6}" y2="{y:.1f}"/>')
        # so o numero leva virgula decimal; a coordenada continua com ponto
        rotulo = f"{g:.2f}".replace(".", ",")
        p.append(f'<text class="g-eixo" x="{L - DIR + 14}" y="{y + 4:.1f}">{rotulo}</text>')

    topo_i = DIAS.index(max(DIAS))

    # --- camada 1: barras e areas de captura ---
    for i, v in enumerate(DIAS):
        x = ESQ + i * PASSO + (PASSO - BARRA) / 2
        y = y_de(v)
        p.append(f'<g class="g-col" data-i="{i}" tabindex="0" role="listitem" '
                 f'aria-label="Dia {i + 1}: {moeda(v)}">')
        # area de captura maior que a barra, pro hover nao exigir pontaria
        p.append(f'<rect class="g-alvo-hover" x="{ESQ + i * PASSO:.1f}" y="{TOPO}" '
                 f'width="{PASSO:.1f}" height="{ALTURA_UTIL:.1f}"/>')
        p.append(f'<path class="g-barra" d="{barra(x, y, BARRA)}"/>')
        p.append(f'<text class="g-dia" x="{x + BARRA / 2:.1f}" y="{PISO + 20}">{i + 1}</text>')
        p.append('</g>')

    # marcador no melhor dia: rotulo direto e seletivo, nao em todo ponto
    xm = ESQ + topo_i * PASSO + PASSO / 2
    ym = y_de(DIAS[topo_i])
    p.append(f'<line class="g-haste" x1="{xm:.1f}" y1="{ym:.1f}" x2="{xm:.1f}" y2="{PISO}"/>')
    p.append(f'<circle class="g-ponto" cx="{xm:.1f}" cy="{ym:.1f}" r="5"/>')

    # --- camada 2: etiquetas, desenhadas por ultimo ---
    # SVG nao tem z-index: quem vem depois fica por cima. Dentro do grupo da
    # barra, a etiqueta ficava atras das barras seguintes.
    p.append('<g class="camada-dicas">')
    for i, v in enumerate(DIAS):
        x = ESQ + i * PASSO + (PASSO - BARRA) / 2
        y = y_de(v)
        rotulo = f"{i + 1} fev &#183; {moeda(v)}"
        largura = 15 + len(rotulo.replace("&#183;", "-")) * 6.9
        cx = x + BARRA / 2
        cx = max(largura / 2, min(cx, L - DIR - largura / 2 + 20))
        p.append(f'<g class="g-dica" data-i="{i}" transform="translate({cx:.1f} {y - 12:.1f})">')
        p.append(f'<rect class="g-dica-caixa" x="{-largura/2:.1f}" y="-30" '
                 f'width="{largura:.1f}" height="30" rx="7"/>')
        p.append(f'<text class="g-dica-txt" x="0" y="-10">{rotulo}</text>')
        p.append('</g>')
    p.append('</g>')

    p.append('</svg>')
    return "".join(p)


def estilos():
    """Liga cada barra a sua etiqueta na outra camada, via :has()."""
    regras = []
    for i in range(len(DIAS)):
        regras.append(
            f'  .g-rpm:has(.g-col[data-i="{i}"]:hover) .g-dica[data-i="{i}"],\n'
            f'  .g-rpm:has(.g-col[data-i="{i}"]:focus-visible) .g-dica[data-i="{i}"]'
            ' { opacity: 1; }')
    return "\n".join(regras)


if __name__ == "__main__":
    print(montar())
