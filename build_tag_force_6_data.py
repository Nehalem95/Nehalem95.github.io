# -*- coding: utf-8 -*-
"""Construye los 60 sobres de Yu-Gi-Oh! 5D's Tag Force 6 desde páginas individuales de Yugipedia.

Uso (en la carpeta del sitio):
  py -m pip install requests beautifulsoup4
  py build_tag_force_6_data.py

Crea tag_force_6_packs.json, un informe JSON y, si se obtienen suficientes páginas,
actualiza TAG_FORCE_6_PACKS en index.html con copia de seguridad. Nunca usa la galería.
"""
from __future__ import annotations
import json, re, time, shutil, sys
from pathlib import Path
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'index.html'
OUT = ROOT / 'tag_force_6_packs.json'
REPORT = ROOT / 'tag_force_6_scrape_report.json'
BASES = ['https://ftp.yugipedia.com/wiki/', 'https://yugipedia.com/wiki/']
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36'}
DELAY = 0.35

NAMES = [
'Novice Monsters','Novice Spells','Novice Traps','Standard Monsters','Standard Spells','Standard Traps','Expert Monsters','Expert Spells','Expert Traps','Grandmaster Catering',
'Super High Impact','Show Under Lock And Key','Rule the World','Special Breakdown','Department of Burning Permission','Colorful Character','Basic Flavor','Melting Point','Memories of Heroic Tales','Master of Ceremony',
'Horns, Wings, Talons, Scales and Fangs','Whispering Chants','Armored Frontliners','Forceful Hardware','Immaculate Emmisaries','House of Darkness','Sign of the Wild','Fly, Biotope','Ruler of Another Land','Coastal Phenomenon',
'Is That Me In Your Heart?','I Burn And Burn And Burn','Bolt from Me','News from Me','Like An Uncut Gem Without Me','Connected to Me','Someone Is Me, Yet I Am Someone As Well','Overlay Network','Resonating Harmony','Plain Flavor',
'Bonds Illuminating the Future','Pulse of A Wild Soul','Great Black Wings','Fragrance of the Pitch-Black Rose','Holy Revolution',"C'mon, Infinite Power!",'Eternal Cage','Continental Circus','Troublesome Guys','Look for the Idols',
'True Time Traveler','Non-Stop Trauma','A Thesis Beyond Time','Feeling the Flow',"It's Really Taboo",'My Wife Plus Plus','High Noon Constellation','Previous Generation','Special Gift','Final Checkered Flag'
]
# Páginas que son colecciones especiales. Se dejan sin expansión si representan conjuntos globales/dinámicos.
GLOBAL_HINTS = ('contains all cards', 'all cards in the game', 'all the cards in the game', 'all rare cards', 'all super rare cards', 'all ultra rare cards')
# Nombre de carta extra que debe quedar delante de las cartas reconstruidas.
EXTRA_FIRST = {
 'Someone Is Me, Yet I Am Someone As Well': ['Ally of Justice Catastor'],
 'Final Checkered Flag': ['Brionac, Dragon of the Ice Barrier', 'Trishula, Dragon of the Ice Barrier'],
}
# Fuentes de colecciones por pack; se usan solo si las páginas fuente pudieron extraerse.
SOURCES = {
 'Someone Is Me, Yet I Am Someone As Well': ['Is That Me In Your Heart?','I Burn And Burn And Burn','Bolt from Me','News from Me','Like An Uncut Gem Without Me','Connected to Me'],
 'Final Checkered Flag': NAMES[:58],
}
# Raridades que se toman de cada pack fuente para estas colecciones.
SOURCE_RARITIES = {
 'Someone Is Me, Yet I Am Someone As Well': {'rare','super rare','ultra rare','rare','super','ultra'},
 'Final Checkered Flag': {'super rare','ultra rare','super','ultra'},
}
TITLE_ALIASES = {
 'High Noon Constellation': ['High Noon Constellation (Tag Force 6)'],
 'Previous Generation': ['Previous Generation (Tag Force 6)'],
 'Special Gift': ['Special Gift (Tag Force 6)'],
 'Final Checkered Flag': ['Final Checkered Flag (Tag Force 6)'],
}

s = requests.Session(); s.headers.update(HEADERS)
def clean(x): return re.sub(r'\s+', ' ', x or '').strip()
def norm(x): return re.sub(r'[^a-z0-9]+','', (x or '').casefold())
def slug(name): return quote(name.replace(' ', '_'), safe="()_,'!-")
def fetch_article(name):
    candidates = list(dict.fromkeys([name] + TITLE_ALIASES.get(name, []) + [name + ' (Tag Force 6)']))
    errors=[]
    for title in candidates:
        for base in BASES:
            url=base+slug(title)
            try:
                r=s.get(url, timeout=25)
                if r.status_code != 200:
                    errors.append(f'{r.status_code} {url}'); continue
                soup=BeautifulSoup(r.text,'html.parser')
                content=soup.select_one('#mw-content-text') or soup.select_one('main') or soup
                h=content.select_one('h1') or soup.select_one('h1')
                actual=clean(h.get_text(' ',strip=True)) if h else title
                if 'does not exist' in clean(content.get_text(' ',strip=True)).lower():
                    errors.append(f'no existe: {url}'); continue
                tables=content.select('table')
                card_table=None; headers=[]
                for table in tables:
                    th=[clean(x.get_text(' ',strip=True)).lower() for x in table.select('tr:first-child th, tr:first-child td')]
                    if 'name' in th and 'rarity' in th:
                        card_table=table; headers=th; break
                if card_table is None:
                    errors.append(f'sin tabla Name/Rarity: {url}'); continue
                idx_name=headers.index('name'); idx_rarity=headers.index('rarity')
                cards=[]
                for tr in card_table.select('tr')[1:]:
                    cells=tr.find_all(['td','th'], recursive=False)
                    if len(cells)<=max(idx_name,idx_rarity): continue
                    namecell=clean(cells[idx_name].get_text(' ',strip=True))
                    rarity=clean(cells[idx_rarity].get_text(' ',strip=True))
                    if not namecell or namecell.lower() in {'name','card name'}: continue
                    if namecell.startswith('[') or namecell.lower() in {'none','not applicable'}: continue
                    cards.append({'name':namecell,'rarity':rarity or 'Unknown','source':actual,'origin':'article'})
                text=clean(content.get_text(' ',strip=True))
                # Best-effort unlock sentence, preserving the source wording.
                unlock=''
                m=re.search(re.escape(actual)+r'.{0,260}?(?:unlocked|available|obtain|purchase).{0,180}',text,re.I)
                if m: unlock=m.group(0)[:320]
                desc=''
                # Keep useful explanatory paragraph(s) before the card table.
                for p in content.select('p'):
                    pt=clean(p.get_text(' ',strip=True))
                    if len(pt)>45 and ('pack' in pt.lower() or 'contains' in pt.lower() or 'cards' in pt.lower()):
                        desc=pt[:900]; break
                return {'ok':True,'url':r.url,'title':actual,'cards':cards,'unlock':unlock,'desc':desc,'pageText':text,'error':None}
            except Exception as e: errors.append(f'{url}: {type(e).__name__}: {e}')
    return {'ok':False,'url':'','title':name,'cards':[],'unlock':'','desc':'','pageText':'','error':' | '.join(errors[-8:])}

def is_global(page):
    t=(page.get('desc','')+' '+page.get('pageText','')).lower()
    return any(h in t for h in GLOBAL_HINTS)
def main():
    print(f'Extrayendo {len(NAMES)} sobres, por páginas individuales (no galería).')
    raw={}; failures=[]
    for i,name in enumerate(NAMES,1):
        print(f'[{i:02}/{len(NAMES)}] {name} ...',end=' ',flush=True)
        p=fetch_article(name); raw[name]=p
        if p['ok']: print(f"OK ({len(p['cards'])} filas) — {p['title']}")
        else: print('NO ENCONTRADO'); failures.append({'pack':name,'error':p['error']})
        time.sleep(DELAY)
    packs=[]
    for i,name in enumerate(NAMES,1):
        p=raw[name]
        cards=p['cards'][:]
        global_pack=is_global(p) if p['ok'] else False
        desc=p['desc']
        reconstruction={'sources':[],'complete':True,'specialCardsFirst':[]}
        if name in SOURCES:
            reconstruction['sources']=SOURCES[name]
            expected = 290 if name == 'Someone Is Me, Yet I Am Someone As Well' else (910 if name == 'Final Checkered Flag' else None)
            if expected and len(cards) < 2:
                reconstruction['articleTableIncomplete'] = True
            if name in EXTRA_FIRST:
                # Ensure article-listed extras are at the very front, preserving source rarity where known.
                extra_names=EXTRA_FIRST[name]
                first=[]
                for en in extra_names:
                    found=next((c for c in cards if norm(c['name'])==norm(en)),None)
                    if found is None and name == 'Someone Is Me, Yet I Am Someone As Well' and norm(en) == norm('Ally of Justice Catastor'):
                        found={'name':en,'rarity':'Ultra','source':name,'origin':'article'}
                    if found: first.append({**found,'origin':'exclusive','source':name})
                # Source reconstruction is limited to the explicitly described rarities.
                allowed=SOURCE_RARITIES.get(name,set())
                rebuilt=[]; seen={norm(c['name']) for c in first}
                for src in SOURCES[name]:
                    sp=raw.get(src,{})
                    if not sp.get('ok'):
                        reconstruction['complete']=False; continue
                    for c in sp.get('cards',[]):
                        rarity=c.get('rarity','').strip()
                        if allowed and rarity.casefold().strip() not in allowed: continue
                        k=norm(c['name'])
                        if k in seen: continue
                        seen.add(k); rebuilt.append({**c,'origin':'reconstructed','source':src})
                # If source articles are missing, keep any explicit cards scraped from this article after extras.
                for c in cards:
                    k=norm(c['name'])
                    if k not in seen:
                        seen.add(k); rebuilt.append({**c,'origin':'article','source':name})
                cards=first+rebuilt
                reconstruction['specialCardsFirst']=[c['name'] for c in first]
                if reconstruction.get('articleTableIncomplete'):
                    reconstruction['complete']=False
                if not reconstruction['complete']:
                    desc=(desc+' ' if desc else '')+'RECONSTRUCCIÓN INCOMPLETA: faltan páginas de uno o más sobres de origen.'
        if global_pack:
            cards=[]
            desc=(desc+' ' if desc else '')+'Colección global/dinámica: no se expande su lista de cartas.'
        packs.append({'num':i,'name':name,'unlock':p['unlock'],'desc':desc,'cards':cards,'kind':'tf6',
                      'articleUrl':p['url'],'articleTitle':p['title'],'scrapeStatus':'ok' if p['ok'] else 'missing',
                      'containsAllCards':global_pack,'reconstruction':reconstruction})
    OUT.write_text(json.dumps(packs,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'total':len(NAMES),'success':sum(p['ok'] for p in raw.values()),'failed':failures,
            'pages':{k:{'ok':v['ok'],'url':v['url'],'title':v['title'],'cardRows':len(v['cards']),'error':v['error']} for k,v in raw.items()}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'\nResultado: {report["success"]}/{len(NAMES)} páginas válidas.')
    print(f'JSON: {OUT.name}\nInforme: {REPORT.name}')
    # Safe integration: only replace the exact TF6 constant if enough individual pages succeeded.
    if report['success'] < 45:
        print('No se modificó index.html: menos de 45 páginas válidas. Revisá el informe y volvé a ejecutar cuando se resuelva el acceso.')
        return 2
    if not INDEX.exists():
        print('No se encontró index.html; se generaron JSON e informe, sin tocar el sitio.')
        return 0
    html=INDEX.read_text(encoding='utf-8')
    pattern=r"const TAG_FORCE_6_PACKS\s*=\s*\[.*?\]\s*\.map\(\(name, i\) => \(\{num:i\+1,name,unlock:'',desc:'Portada de la galería de sobres de Tag Force 6\.',cards:\[\],kind:'tf6'\}\)\);"
    replacement='const TAG_FORCE_6_PACKS = '+json.dumps(packs,ensure_ascii=False,separators=(',',':'))+';'
    new,count=re.subn(pattern,lambda _:replacement,html,count=1,flags=re.S)
    if count!=1:
        print('No se encontró exactamente la constante antigua de TF6; no se modificó index.html.')
        return 3
    backup=INDEX.with_name('index.html.backup-before-tf6-data')
    if not backup.exists(): shutil.copy2(INDEX,backup)
    INDEX.write_text(new,encoding='utf-8')
    print(f'Actualizado index.html. Copia de seguridad: {backup.name}')
    print('Las cartas exclusivas/reveladas por el artículo se colocan antes de las cartas reconstruidas; revise el informe antes de publicar.')
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: print('\nCancelado por el usuario.'); sys.exit(130)
