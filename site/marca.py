"""Gera os traçados da marca Acerolab: a fruta trilobada e o play arredondado."""
import math

def suavizar(pontos, fechado=True):
    """Catmull-Rom -> cubica de Bezier, para uma silhueta organica e precisa."""
    n = len(pontos)
    d = f"M{pontos[0][0]:.2f} {pontos[0][1]:.2f}"
    limite = n if fechado else n - 1
    for i in range(limite):
        p0 = pontos[(i - 1) % n]
        p1 = pontos[i % n]
        p2 = pontos[(i + 1) % n]
        p3 = pontos[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}"
    return d + ("Z" if fechado else "")


def fruta(cx, cy, raio, lobulos=3, amplitude=0.045, giro=-math.pi / 2, passos=120):
    """Circulo modulado por cos(3O): os tres gomos rasos da acerola."""
    pts = []
    for i in range(passos):
        t = 2 * math.pi * i / passos
        r = raio * (1 + amplitude * math.cos(lobulos * t + giro))
        # leve achatamento vertical, como a fruta real
        pts.append((cx + r * math.cos(t), cy + r * 0.965 * math.sin(t)))
    return suavizar(pts)


def play(cx, cy, raio, canto=0.19):
    """Triangulo de play com cantos arredondados, inscrito num circulo."""
    vs = [(cx + raio * math.cos(math.radians(a)), cy + raio * math.sin(math.radians(a)))
          for a in (0, 120, 240)]
    r = raio * canto
    d = ""
    for i in range(3):
        a, b, c = vs[i], vs[(i + 1) % 3], vs[(i + 2) % 3]
        for viz, destino in ((c, "entrada"), (b, "saida")):
            vx, vy = viz[0] - a[0], viz[1] - a[1]
            comp = math.hypot(vx, vy)
            p = (a[0] + vx / comp * r, a[1] + vy / comp * r)
            if destino == "entrada":
                d += (f"M{p[0]:.2f} {p[1]:.2f}" if i == 0 else f"L{p[0]:.2f} {p[1]:.2f}")
                inicio = p
            else:
                d += f"Q{a[0]:.2f} {a[1]:.2f} {p[0]:.2f} {p[1]:.2f}"
    return d + "Z"


def folha(cx, cy, comp, larg, ang):
    """Folha simples: duas curvas espelhadas a partir do pedunculo."""
    a = math.radians(ang)
    px, py = cx + comp * math.cos(a), cy + comp * math.sin(a)
    nx, ny = -math.sin(a) * larg, math.cos(a) * larg
    mx, my = cx + (px - cx) * 0.5, cy + (py - cy) * 0.5
    return (f"M{cx:.2f} {cy:.2f}"
            f"Q{mx + nx:.2f} {my + ny:.2f} {px:.2f} {py:.2f}"
            f"Q{mx - nx:.2f} {my - ny:.2f} {cx:.2f} {cy:.2f}Z")


# ── a marca ────────────────────────────────────────────────────
# A fruta é um círculo limpo (não a silhueta trilobada da versão anterior):
# fica mais legível no tamanho pequeno, que é onde a marca mais aparece.
# O play é recortado dela pela regra `evenodd` — não é um triângulo branco
# por cima, é buraco de verdade, então funciona sobre qualquer fundo.

CX, CY, R = 50.0, 58.0, 38.0


def circulo(cx, cy, r):
    """Círculo como path, para poder entrar no mesmo `d` do recorte."""
    return (f"M{cx - r:.2f} {cy:.2f}"
            f"A{r:.2f} {r:.2f} 0 1 0 {cx + r:.2f} {cy:.2f}"
            f"A{r:.2f} {r:.2f} 0 1 0 {cx - r:.2f} {cy:.2f}Z")


# O play sobe um pouco à direita do centro geométrico: triângulo centrado na
# conta parece deslocado para a esquerda, porque a massa dele fica atrás.
raio_play = R * 0.42
print("FRUTA=" + circulo(CX, CY, R))
print("PLAY=" + play(CX + raio_play * 0.16, CY, raio_play, canto=0.22))
print("TALO=M50 22 C50 10 58 4 70 3")
print("FOLHA=M50 20 C36 12 24 16 20 26 C32 34 44 31 50 20Z")
print("VIEWBOX=8 -1 84 101")
