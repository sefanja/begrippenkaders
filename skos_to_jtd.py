import os
import shutil
from rdflib import Graph, Namespace, RDF, SKOS, DCTERMS
from slugify import slugify # pip install python-slugify

# Configuratie
INPUT_FILE = "begrippenkader.ttl"
OUTPUT_DIR = "docs" # GitHub Pages kijkt standaard in /docs of root

def main():
    print(f"Laden van {INPUT_FILE}...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")

    # 1. Schoonmaak
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # 2. Indexeer alle concepten (URI -> Info)
    # We hebben dit nodig om de LABEL van de parent te vinden
    concept_map = {}
    
    # Eerst alle labels verzamelen
    for s in g.subjects(RDF.type, SKOS.Concept):
        pref_label = g.value(s, SKOS.prefLabel, any=False) or "Naamloos"
        concept_map[str(s)] = {
            "uri": str(s),
            "label": str(pref_label),
            "slug": slugify(str(pref_label)),
            "broader": []
        }
    
    # Ook het ConceptScheme ophalen (als Root)
    scheme = next(g.subjects(RDF.type, SKOS.ConceptScheme), None)
    scheme_label = "Begrippenkader"
    if scheme:
        scheme_label = str(g.value(scheme, DCTERMS.title) or g.value(scheme, SKOS.prefLabel) or "Begrippenkader")
        # Maak de index pagina (Homepage)
        create_index_page(scheme_label, g, scheme)

    # 3. Relaties leggen
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        
        # Zoek parents (broader)
        for parent in g.objects(subject, SKOS.broader):
            if str(parent) in concept_map:
                info['broader'].append(concept_map[str(parent)]['label'])
        
    # 4. Bestanden genereren
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        generate_jtd_markdown(g, subject, info, concept_map, scheme_label)

    print("Klaar! Run 'bundle exec jekyll serve' of push naar GitHub.")

def create_index_page(title, g, scheme):
    """Maakt de homepage (index.md)"""
    desc = ""
    if scheme:
        desc = g.value(scheme, DCTERMS.description) or ""
    
    content = f"""---
layout: default
title: {title}
---

# {title}

{desc}

Welkom in het begrippenkader. Gebruik de navigatie links of de zoekbalk bovenin.
"""
    with open(f"{OUTPUT_DIR}/index.md", "w", encoding="utf-8") as f:
        f.write(content)

def generate_jtd_markdown(g, s, info, concept_map, root_name):
    label = info['label']
    
    # Bepaal de Parent voor Just the Docs navigatie
    # JtD ondersteunt maar 1 parent in de URL structuur. We pakken de eerste broader.
    # Als er geen broader is, hangen we hem onder de Homepage (Root)
    parent_field = ""
    if info['broader']:
        parent_name = info['broader'][0] # Pak de eerste
        parent_field = f"parent: {parent_name}"
    else:
        parent_field = f"parent: {root_name}"

    # Front Matter (De magie van Just the Docs)
    md = f"""---
layout: default
title: {label}
{parent_field}
---

# {label}
"""
    # De rest is standaard NL-SBB content (hetzelfde als vorig script)
    definition = g.value(s, SKOS.definition)
    scope_note = g.value(s, SKOS.scopeNote)
    alt_labels = [str(l) for l in g.objects(s, SKOS.altLabel)]
    
    if definition:
        md += f"\n## Definitie\n{definition}\n"
    if scope_note:
        md += f"\n## Toelichting\n{scope_note}\n"

    # Tabelletje
    md += "\n## Eigenschappen\n\n"
    md += "| Eigenschap | Waarde |\n| :--- | :--- |\n"
    if alt_labels:
        md += f"| Alternatieve termen | {', '.join(alt_labels)} |\n"
    md += f"| URI | `{str(s)}` |\n\n"

    # Relaties expliciet tonen (omdat menu soms beperkt is)
    broader = get_links(g, s, SKOS.broader, concept_map)
    narrower = get_links(g, s, SKOS.narrower, concept_map)
    related = get_links(g, s, SKOS.related, concept_map)

    if broader or narrower or related:
        md += "\n## Relaties\n"
        if broader: md += f"* **Bovenliggend:** {', '.join(broader)}\n"
        if narrower: md += f"* **Onderliggend:** {', '.join(narrower)}\n"
        if related:  md += f"* **Gerelateerd:** {', '.join(related)}\n"

    # Opslaan
    filename = f"{info['slug']}.md"
    with open(f"{OUTPUT_DIR}/{filename}", "w", encoding="utf-8") as f:
        f.write(md)

def get_links(g, subject, predicate, concept_map):
    links = []
    for obj in g.objects(subject, predicate):
        uri = str(obj)
        if uri in concept_map:
            # Voor Just the Docs linken we naar de generated URL (vaak bestandsnaam zonder .md)
            lbl = concept_map[uri]['label']
            slug = concept_map[uri]['slug']
            links.append(f"[{lbl}]({slug}.html)")
        else:
            links.append(str(obj))
    return links

if __name__ == "__main__":
    main()
