"""Floor remarks from the Congressional Record (GovInfo): Ukraine aid (Jan 2023 to Apr 2024) and the Respect for
Marriage Act (June to Dec 2022). Change the day range and title pattern below for a new topic.

Step 1 lists each day's Record from the GovInfo sitemap and reads its MODS metadata, which names every speaker
with a Bioguide ID. Step 2 downloads debates whose titles touch Ukraine or the supplemental and splits them into
speaker turns. Stances were then hand-coded into data/floor_statements.csv (one row per member per topic); keyword rules alone
labeled only about a third of members correctly, so every stance was read by a person.

No API key is needed: www.govinfo.gov serves the sitemaps, MODS files and HTML directly. Downloads are cached
under /tmp/crec (about 450 MB of MODS for this window). Shown on the Campaign Statements page.
"""

# --- Step 0: list days, then download MODS ---
# for y in 2023 2024: curl https://www.govinfo.gov/sitemap/CREC_${y}_sitemap.xml
# for each CREC-YYYY-MM-DD up to 2024-04-23: curl https://www.govinfo.gov/metadata/pkg/<id>/mods.xml

# --- Step 1: parse MODS ---
import re, glob, json, sys
from xml.etree import ElementTree as ET
NS={"m":"http://www.loc.gov/mods/v3"}
rows=[]
for f in sorted(glob.glob("/tmp/crec/mods/*.xml")):
    try: root=ET.parse(f).getroot()
    except Exception as e: continue
    for g in root.findall("m:relatedItem[@type='constituent']", NS):
        title=(g.findtext("m:titleInfo/m:title", default="", namespaces=NS) or "").strip()
        part=g.findtext("m:titleInfo/m:partName", default="", namespaces=NS)
        url=None
        for u in g.findall("m:location/m:url", NS):
            if u.get("displayLabel")=="HTML rendition": url=u.text
        date=re.search(r"CREC-(\d{4}-\d{2}-\d{2})", f).group(1)
        spk=[]
        for c in g.iter("{http://www.loc.gov/mods/v3}congMember"):
            if c.get("role")=="SPEAKING":
                parsed=[n.text for n in c.findall("m:name", NS) if n.get("type")=="parsed"]
                spk.append(dict(bioguide=c.get("bioGuideId"), chamber=c.get("chamber"), party=c.get("party"),
                                state=c.get("state"), parsed=parsed[0] if parsed else None))
        rows.append(dict(date=date, title=title, part=part, url=url, speakers=spk))
json.dump(rows, open("/tmp/crecwork/granules.json","w"))
print(len(rows))


# --- Step 2: fetch debates and split speaker turns ---
import json, re, os, html, hashlib, subprocess, concurrent.futures as cf
g=json.load(open("/tmp/crecwork/granules.json"))
PAT=re.compile(r"UKRAIN|SUPPLEMENTAL|NATIONAL SECURITY|FOREIGN AID|PUTIN|RUSSIA", re.I)
EXCL=re.compile(r"HOUSING|DOMESTIC|DISASTER", re.I)
cand=[x for x in g if PAT.search(x["title"]) and not EXCL.search(x["title"]) and x["url"] and x["speakers"]]
os.makedirs("/tmp/crec/html", exist_ok=True)
def get(x):
    p="/tmp/crec/html/"+x["url"].rsplit("/",1)[1]
    if not os.path.exists(p) or os.path.getsize(p)==0:
        subprocess.run(["curl","-sS","--max-time","60",x["url"],"-o",p])
    return p
with cf.ThreadPoolExecutor(6) as ex: paths=list(ex.map(get,cand))
turns=[]
for x,p in zip(cand,paths):
    raw=open(p,encoding="utf-8",errors="ignore").read()
    m=re.search(r"<pre>(.*)</pre>",raw,re.S); txt=html.unescape(re.sub(r"<[^>]+>","",m.group(1) if m else raw))
    txt=re.sub(r"\[\[Page [^\]]*\]\]","",txt)
    # speaker turns start at line beginnings like "  Mr. DIAZ-BALART. " ; also "The SPEAKER pro tempore." etc
    names={s["parsed"]:s for s in x["speakers"] if s["parsed"]}
    alt="|".join(sorted((re.escape(n) for n in names), key=len, reverse=True))
    if not alt: continue
    starts=list(re.finditer(r"\n\s{2,}(%s|The (?:SPEAKER|PRESIDING OFFICER|CHAIR|ACTING PRESIDENT)[^.\n]*|The Clerk|The legislative clerk)(?: of [A-Za-z ]+)?\.\s"%alt, txt))
    for i,s in enumerate(starts):
        who=s.group(1); end=starts[i+1].start() if i+1<len(starts) else len(txt)
        if who not in names: continue
        body=re.sub(r"\s+"," ",txt[s.end():end]).strip()
        turns.append(dict(date=x["date"], title=x["title"], part=x["part"], url=x["url"], **names[who], text=body))
json.dump(turns, open("/tmp/crecwork/turns.json","w"))
print(len(cand), len(turns))
