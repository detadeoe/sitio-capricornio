"""Robot de noticias del blog OEI.
Busca noticias en Google Noticias (RSS) por tema y escribe noticias.json.
Lo ejecuta GitHub Actions cada 6 horas (.github/workflows/noticias.yml).
"""
import json, re, sys, html, urllib.parse, urllib.request, datetime, email.utils
import xml.etree.ElementTree as ET

TEMAS = [
    ("mineria",    "Minería en México",          'minería México OR "industria minera" México'),
    ("proyectos",  "Nuevos proyectos mineros",   '"nueva mina" OR "proyecto minero" OR "exploración minera" OR "inversión minera" México'),
    ("acero",      "Siderurgia y acero",         'siderurgia OR acerera OR "industria del acero" México'),
    ("bajio",      "Industria en el Bajío",      'Guanajuato OR Irapuato OR Bajío industria OR inversión OR planta'),
    ("clientes",   "Grandes clientes",           'Peñoles OR Fresnillo OR Pemex OR "Grupo México" OR Ternium OR Minera Saucito'),
]
POR_TEMA = 30
UA = {"User-Agent": "Mozilla/5.0 (OEI noticias; +https://capricornioirapuato.com)"}

def rss_url(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:14d", "hl": "es-419", "gl": "MX", "ceid": "MX:es-419"})

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
            seen.add(k); uniq.append(x)
        data["temas"].append({"id": key, "nombre": nombre, "items": uniq[:POR_TEMA]})
        total += len(uniq[:POR_TEMA])
        print(key, len(uniq[:POR_TEMA]))
    if total == 0:
        print("sin noticias; no se sobrescribe el archivo", file=sys.stderr); sys.exit(1)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "noticias.json")
