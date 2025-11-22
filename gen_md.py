import os
import shutil
import glob
from rdflib import Graph, Namespace, RDF, SKOS, DCTERMS, RDFS, URIRef, FOAF
from slugify import slugify

# --- CONFIGURATIE ---
INPUT_DIR = "begrippenkaders" # Of de map waar je TTL(s) staan
OUTPUT_DIR = "docs"
BASE_PERMALINK = "/begrippenkaders" # We houden de URL schoon en plat

# Namespaces
PROV = Namespace("http://www.w3.org/ns/prov#")
ADMS = Namespace("http://www.w3.org/ns/adms#")

def main():
    print(f"Laden van begrippen...")
    
    # 1. Graph laden
    g = Graph()
    # Pakt alle .ttl files in de map (handig als je het ooit splitst, maar toch 1 geheel wilt)
    ttl_files = glob.glob(os.path.join(INPUT_DIR, "*.ttl"))
    
    if not ttl_files:
        print("Geen .ttl bestanden gevonden!")
        return

    for file_path in ttl_files:
        g.parse(file_path, format="turtle")

    # 2. Output schoonmaken (niet dus)

    # 3. Maak de Homepage (index.md)
    # We doen dit eerst, zodat hij nav_order: 0 krijgt
    create_homepage()

    # 4. Indexeren van alle concepten
    concept_map = {}
    for s in g.subjects(RDF.type, SKOS.Concept):
        pref_label = g.value(s, SKOS.prefLabel, any=False) or "Naamloos"
        slug = slugify(str(pref_label))
        
        concept_map[str(s)] = {
            "uri": str(s),
            "label": str(pref_label),
            "slug": slug,
            "permalink": f"{BASE_PERMALINK}/{slug}/",
            "broader": []
        }

    # 5. Relaties leggen (Wie is mijn ouder?)
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        for parent in g.objects(subject, SKOS.broader):
            if str(parent) in concept_map:
                info['broader'].append(concept_map[str(parent)]['label'])

    # 6. Markdown Genereren
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        generate_markdown(g, subject, info, concept_map)

    print(f"Klaar! {len(concept_map)} begrippen gegenereerd in de root.")

def create_homepage():
    """Maakt de index.md die als 'Home' fungeert"""
    md = """---
layout: default
title: Home
nav_exclude: true
permalink: /
---

# Begrippenkader Energiesysteembeheer

Welkom op de begrippenlijst. Hieronder vindt u de definities zoals vastgesteld in het stelsel.
Gebruik het menu aan de linkerkant om door de hoofd-onderwerpen te navigeren.
"""
    with open(os.path.join(OUTPUT_DIR, "index.md"), "w", encoding="utf-8") as f:
        f.write(md)

def generate_markdown(g, s, info, concept_map):
    label = info['label']
    
    # --- DE TRUC VOOR DE NAVIGATIE ---
    # Heeft het begrip een ouder (broader)?
    # JA -> Parent veld invullen -> Hij wordt ingeklapt
    # NEE -> Geen Parent veld -> Hij wordt een TOP ITEM in de sidebar
    
    parent_line = ""
    if info['broader']:
        # Pak de eerste parent
        parent_line = f"parent: {info['broader'][0]}"
        has_children_line = "" # Kinderen krijgen standaard geen pijltje tenzij ze zelf kinderen hebben
        
        # Check of IK kinderen heb (voor het pijltje)
        if list(g.subjects(SKOS.broader, s)):
             has_children_line = "has_children: true"
        else:
             has_children_line = "has_children: false"
    else:
        # DIT IS EEN TOP CONCEPT
        # Geen parent regel!
        # Wel has_children: true, want top concepten hebben per definitie kinderen (meestal)
        parent_line = "" 
        has_children_line = "has_children: true"

    # Front Matter
    md = f"""---
layout: default
title: {label}
{parent_line}
{has_children_line}
permalink: {info['permalink']}
---

# {label}
"""

    # --- Content (NL-SBB Standaard) ---
    definition = g.value(s, SKOS.definition)
    if definition: md += f"\n## Definitie\n{definition}\n"

    scope_notes = list(g.objects(s, SKOS.scopeNote))
    if scope_notes:
        md += "\n## Toelichting\n"
        for note in scope_notes: md += f"{note}\n\n"

    # Terminologie Tabel
    alt_labels = [str(l) for l in g.objects(s, SKOS.altLabel)]
    if alt_labels:
        md += "\n## Terminologie\n\n"
        md += "| Type | Term |\n| :--- | :--- |\n"
        md += f"| Voorkeursterm | {label} |\n"
        for alt in alt_labels: md += f"| Synoniem | {alt} |\n"
        md += "\n"

    # Relaties
    broader = get_internal_links(g, s, SKOS.broader, concept_map)
    narrower = get_internal_links(g, s, SKOS.narrower, concept_map)
    related = get_internal_links(g, s, SKOS.related, concept_map)

    if broader or narrower or related:
        md += "\n## Relaties\n"
        if broader: md += f"* **Bovenliggend:** {', '.join(broader)}\n"
        if narrower: md += f"* **Onderliggend:** {', '.join(narrower)}\n"
        if related:  md += f"* **Gerelateerd:** {', '.join(related)}\n"

    # Metadata Tabel
    sources = get_smart_sources(g, s)
    if sources:
        md += "\n## Metadata\n\n| Eigenschap | Waarde |\n| :--- | :--- |\n"
        md += f"| Bron | {', '.join(sources)} |\n"
        md += f"| URI | `{str(s)}` |\n"
        md += "\n"

    # Opslaan in de root van docs/
    filename = f"{info['slug']}.md"
    with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
        f.write(md)

# --- Helper Functies (Kopieer deze uit de vorige scripts) ---
def get_internal_links(g, subject, predicate, concept_map):
    links = []
    for obj in g.objects(subject, predicate):
        uri = str(obj)
        if uri in concept_map:
            lbl = concept_map[uri]['label']
            # Link naar permalink
            links.append(f"[{lbl}]({concept_map[uri]['permalink']})")
    return links

def get_smart_sources(g, subject):
    # Gebruik de logica uit mijn antwoord over dct:source (met FOAF check)
    # Zie: "Zou het niet gemakkelijk zijn om dit Python-script..." antwoord
    items = []
    # (Voeg hier de body toe van get_smart_sources die we eerder maakten)
    # ...
    return items

if __name__ == "__main__":
    main()