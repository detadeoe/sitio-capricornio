"""Robot de noticias del blog OEI.
Busca noticias en Google Noticias (RSS) por tema y escribe noticias.json.
Lo ejecuta GitHub Actions cada 6 horas (.github/workflows/noticias.yml).
"""
import json, re, sys, html, urllib.parse, urllib.request, datetime, email.utils
import xml.etree.ElementTree as ET

TEMAS = [
    ("minas",      "Minería",      '("nueva mina" OR "proyecto minero" OR "construcción de mina" OR "exploración minera" OR "reactivar mina" OR "inicia operaciones") México'),
    ("plantas",    "Inversiones industriales",  '"nueva planta" OR "ampliación de planta" OR "inversión industrial" OR "parque industrial" México'),
    ("acero",      "Acero",           'acerera OR siderúrgica inversión OR ampliación OR "nueva planta" OR "alto horno" México'),
    ("licitaciones","Licitaciones",     '(licitación OR "adjudica contrato" OR "contrato de mantenimiento") (minera OR Pemex OR CFE OR industrial OR planta) México'),
    ("jugadores",  "Empresas del sector",             'Peñoles OR Fresnillo OR "Grupo México" OR Ternium OR "Minera Frisco" OR "First Majestic" inversión OR proyecto OR mina'),
    ("bajio",      "Bajío",            '(Guanajuato OR Irapuato OR Celaya OR Salamanca OR Silao OR Querétaro OR "San Luis Potosí" OR Zacatecas OR Aguascalientes) (planta OR mina OR "parque industrial" OR inversión industrial)'),
]
# Palabras que indican oportunidad de negocio (peso) y palabras a descartar
OPORTUNIDAD = {
    r"nueva mina|nuevo proyecto|proyecto minero|mina nueva": 4, r"construcci[oó]n|construir[aá]?|edificar": 3,
    r"inversi|invertir|invierte|millones de d[oó]lares|mdd|mdp|millones": 3, r"empleos": 1, r"ampliaci[oó]n|expansi[oó]n|ampl[ií]a": 3,
    r"licitaci[oó]n|contrato|adjudica|concurso": 3, r"nueva planta|planta nueva|parque industrial|nave industrial": 4,
    r"arranque|inicia(r[aá])? operaciones|inaugura|pone en marcha|reactiva|reapertura": 3,
    r"exploraci[oó]n|permiso|autoriza|aprueba|manifestaci[oó]n de impacto": 2, r"proyecto": 1, r"mina|minera|minero": 1,
    r"acerera|sider[uú]rgica|acero|fundici[oó]n|alto horno": 1, r"mantenimiento|maquinaria|equipo|gr[uú]a": 1,
}
DESCARTAR = r"asesin|homicid|balacera|narco|secuestr|desaparec|fútbol|futbol|liga mx|elecci[oó]n|morena|senador|diputad|horóscopo|clima hoy|farándula|celebridad|ley ind[ií]gena"
CERCA = r"guanajuato|irapuato|celaya|le[oó]n,? gto|le[oó]n guanajuato|salamanca|silao|baj[ií]o|quer[eé]taro|san luis potos[ií]|aguascalientes|zacatecas|michoac[aá]n"

EXTRANJERO = r"costa rica|nicaragua|san juan prepara|los azules|galicia|paradela|panam[aá]|estados unidos|texas|canad[aá]|per[uú]|\bminem\b|argentin|chile|colombia|bolivia|ecuador|espa[ñn]a|canarias|ciudadreal|castilla|andaluc|provincia de|\bnoa\b|neuqu[eé]n|mendoza|r[ií]o negro|venezuel|guatemal|honduras|brasil"
FUENTES_FUERA = r"facebook|tiktok|youtube|instagram|\.ar$|\.pe$|\.es$|\.cl$|\.co$|rumbo minero|lt9|editorial rn|canarias7|la raz[oó]n$|tendencia de noticia"

INDUSTRIA = r"mina|miner|planta|industr|acer[oa]|sider[uú]rg|fundici|manufactur|f[aá]brica|pemex|cfe|refiner|nave|automotr|energ[eé]t|gasoducto|el[eé]ctric|maquinaria|metal|cobre|plata|oro\b|zinc|litio|hidr[aá]ulic|cementer|ternium|arcelor|ahmsa|pe[ñn]oles|fresnillo|grupo m[eé]xico|frisco|majestic|tren|ferrocarril|puerto|presa|acueducto"

def puntuar(x):
    t = x["t"].lower()
    if re.search(DESCARTAR, t) or re.search(EXTRANJERO, t) or re.search(FUENTES_FUERA, (x.get("s") or "").lower()): return -1, False
    if not re.search(INDUSTRIA, t): return 0, False
    s = sum(w for pat, w in OPORTUNIDAD.items() if re.search(pat, t))
    return s, bool(re.search(CERCA, t))

POR_TEMA = 30
MIN_PUNTOS = 2
UA = {"User-Agent": "Mozilla/5.0 (OEI noticias; +https://capricornioirapuato.com)"}

def rss_url(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:21d", "hl": "es-419", "gl": "MX", "ceid": "MX:es-419"})

def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        try:
            dt = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
            date = dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            date = ""
        if title and link.startswith("https://"):
            out.append({"t": html.unescape(title), "s": html.unescape(source), "u": link, "d": date})
    return out

def norm(t):
    return re.sub(r"[^a-z0-9áéíóúñ ]", "", t.lower())[:90]

def main(path):
    data = {"actualizado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "temas": []}
    total = 0
    for key, nombre, q in TEMAS:
        try:
            req = urllib.request.Request(rss_url(q), headers=UA)
            items = parse(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            print("error", key, e, file=sys.stderr); items = []
        seen, uniq = set(), []
        for x in sorted(items, key=lambda x: x["d"], reverse=True):
            k = norm(x["t"])
            if k in seen: continue
            seen.add(k)
            p, cerca = puntuar(x)
            if p < MIN_PUNTOS: continue
            x["o"] = p
            if cerca: x["c"] = 1
            uniq.append(x)
        data["temas"].append({"id": key, "nombre": nombre, "items": uniq[:POR_TEMA]})
        total += len(uniq[:POR_TEMA])
        print(key, len(uniq[:POR_TEMA]))
    if total == 0:
        print("sin noticias; no se sobrescribe el archivo", file=sys.stderr); sys.exit(1)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "noticias.json")
