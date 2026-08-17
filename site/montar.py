"""Junta wordmark vetorizado + marca + fontes e injeta no HTML."""
import base64, json, math, pathlib, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.misc.transform import Transform

AQUI = pathlib.Path(__file__).parent


def wordmark(caminho, peso, palavra, altura=100.0):
    fonte = TTFont(caminho)
    if "fvar" in fonte:
        fonte = instancer.instantiateVariableFont(fonte, {"wght": peso})
    upm = fonte["head"].unitsPerEm
    esc = altura / upm
    glifos, cmap, hmtx = fonte.getGlyphSet(), fonte.getBestCmap(), fonte["hmtx"]
    partes, x = [], 0.0
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for ch in palavra:
        nome = cmap[ord(ch)]
        t = Transform(esc, 0, 0, -esc, x * esc, altura)
        pen = SVGPathPen(glifos)
        glifos[nome].draw(TransformPen(pen, t))
        if pen.getCommands():
            partes.append(pen.getCommands())
        bp = BoundsPen(glifos)
        glifos[nome].draw(TransformPen(bp, t))
        if bp.bounds:
            bx0, by0, bx1, by1 = bp.bounds
            x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
        x += hmtx[nome][0]
    return {"d": " ".join(partes), "bbox": [x0, y0, x1, y1]}


def b64(caminho):
    return base64.b64encode(pathlib.Path(caminho).read_bytes()).decode()


def main():
    """O que o script faz quando rodado direto."""
    marca = {}
    for linha in (AQUI / "marca.txt").read_text().strip().splitlines():
        chave, valor = linha.split("=", 1)
        marca[chave] = valor

    wm = wordmark(AQUI / "Outfit.ttf", 800, "acerolab")
    bx0, by0, bx1, by1 = wm["bbox"]
    pad = 2
    vb = f"{bx0 - pad:.2f} {by0 - pad:.2f} {bx1 - bx0 + pad * 2:.2f} {by1 - by0 + pad * 2:.2f}"

    # imagens de assets_ref/ viram __IMG_NOME__ como data URI
    imagens = {}
    pasta = AQUI / "assets_limpo"
    MIME = {".webp": "image/webp", ".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4"}
    if pasta.is_dir():
        for arq in sorted(pasta.iterdir()):
            if arq.suffix not in MIME:
                continue
            prefixo = "__VID_" if arq.suffix == ".mp4" else "__IMG_"
            chave = prefixo + arq.stem.replace("-", "_").replace(".", "_").upper() + "__"
            imagens[chave] = f"data:{MIME[arq.suffix]};base64," + b64(arq)

    import grafico

    favicon_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="5 -12 110 128">'
        '<path d="%s" fill="#3F6B4E"/>'
        '<path d="%s" fill="none" stroke="#3F6B4E" stroke-width="4.6" stroke-linecap="round"/>'
        '<path d="%s %s" fill-rule="evenodd" fill="#E8253D"/>'
        '</svg>'
    ) % (marca["FOLHA"], marca["TALO"], marca["FRUTA"], marca["PLAY"])

    subs = {
        **imagens,
        "__FAVICON__": "data:image/svg+xml," + __import__("urllib.parse", fromlist=["quote"]).quote(favicon_svg),
        "__GRAFICO_RPM__": grafico.montar(),
        "__GRAFICO_CSS__": grafico.estilos(),
        "__WORDMARK_D__": wm["d"],
        "__WORDMARK_VB__": vb,
        "__WORDMARK_RATIO__": f"{(bx1 - bx0 + pad * 2) / (by1 - by0 + pad * 2):.4f}",
        "__FRUTA__": marca["FRUTA"],
        "__PLAY__": marca["PLAY"],
        "__FOLHA__": marca["FOLHA"],
        "__MARCA_VB__": marca["VIEWBOX"],
        "__TALO__": marca["TALO"],
        "__FONT_DISPLAY__": b64(AQUI / "outfit.woff2"),
        "__FONT_TEXTO__": b64(AQUI / "news.woff2"),
    }

    origem = AQUI / (sys.argv[1] if len(sys.argv) > 1 else "acerolab.html")
    html = origem.read_text()
    faltando = [k for k in subs if k not in html]
    for k, v in subs.items():
        html = html.replace(k, v)
    saida = AQUI / (origem.stem + ".build.html")
    saida.write_text(html)

    print(f"wordmark viewBox: {vb}")
    print(f"placeholders nao encontrados: {faltando or 'nenhum'}")
    print(f"gerado: {saida}  ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
