import os
import shutil
import glob
from rdflib import Graph, Namespace, RDF, SKOS, DCTERMS, RDFS, URIRef, FOAF
from slugify import slugify

# --- CONFIGURATIE ---
INPUT_DIR = "begrippenkaders" # Map met .ttl bestanden
OUTPUT_DIR = "docs"           # Output voor GitHub Pages
BASE_PERMALINK = "/begrippenkaders" # De start van je URL

# Namespaces
PROV = Namespace("http://www.w3.org/ns/prov#")
ADMS = Namespace("http://www.w3.org/ns/adms#")

def main():
    print(f"Zoeken naar TTL bestanden in '{INPUT_DIR}'...")
    
    # 1. Alles inladen in één Graph (zodat cross-linking werkt)
    g = Graph()
    ttl_files = glob.glob(os.path.join(INPUT_DIR, "*.ttl"))
    
    if not ttl_files:
        print("Geen .ttl bestanden gevonden!")
        return

    for file_path in ttl_files:
        print(f" - Laden: {file_path}")
        g.parse(file_path, format="turtle")

    # 2. Output schoonmaken
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # 3. Indexeer ConceptSchemes (Dit worden de 'Hoofdstukken')
    # We koppelen URI -> Mapnaam (slug)
    schemes = {}
    for s in g.subjects(RDF.type, SKOS.ConceptScheme):
        label = g.value(s, DCTERMS.title) or g.value(s, SKOS.prefLabel) or "Onbekend Kader"
        slug = slugify(str(label))
        schemes[str(s)] = {
            "uri": str(s),
            "label": str(label),
            "slug": slug,
            "description": g.value(s, DCTERMS.description) or ""
        }
    
    print(f"Gevonden kaders: {', '.join([x['label'] for x in schemes.values()])}")

    # 5. Maak per Scheme een submap en index pagina
    for s_uri, s_info in schemes.items():
        scheme_dir = os.path.join(OUTPUT_DIR, s_info['slug'])
        os.makedirs(scheme_dir, exist_ok=True)
        create_scheme_index(scheme_dir, s_info)

    # 6. Indexeer Concepten en koppel ze aan hun Scheme
    concept_map = {}
    for s in g.subjects(RDF.type, SKOS.Concept):
        pref_label = g.value(s, SKOS.prefLabel, any=False) or "Naamloos"
        slug = slugify(str(pref_label))
        
        # Bepaal bij welk schema dit hoort (skos:inScheme of skos:topConceptOf)
        # Als een begrip in meerdere schema's zit, pakken we de eerste voor de URL-structuur
        in_scheme = g.value(s, SKOS.inScheme) or g.value(s, SKOS.topConceptOf)
        
        scheme_slug = "algemeen" # Fallback
        if in_scheme and str(in_scheme) in schemes:
            scheme_slug = schemes[str(in_scheme)]['slug']
        
        # URL wordt nu: /begrippenkaders/{schema}/{begrip}/
        permalink = f"{BASE_PERMALINK}/{scheme_slug}/{slug}/"
        
        concept_map[str(s)] = {
            "uri": str(s),
            "label": str(pref_label),
            "slug": slug,
            "scheme_slug": scheme_slug, # Nodig voor bestandslocatie
            "permalink": permalink,
            "broader": [],
            "in_scheme_uri": str(in_scheme) if in_scheme else None
        }

    # 7. Relaties leggen (Parents bepalen)
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        for parent in g.objects(subject, SKOS.broader):
            if str(parent) in concept_map:
                info['broader'].append(concept_map[str(parent)]['label'])

    # 8. Bestanden genereren
    for uri, info in concept_map.items():
        subject = next(s for s in g.subjects() if str(s) == uri)
        
        # Bepaal de naam van de 'Root' van dit kader voor de kruimelpad/navigatie
        root_name = "Algemeen"
        if info['in_scheme_uri'] and info['in_scheme_uri'] in schemes:
            root_name = schemes[info['in_scheme_uri']]['label']
            
        generate_markdown(g, subject, info, concept_map, root_name)

    print("Klaar! Website gegenereerd.")

def create_scheme_index(folder, s_info):
    """Maakt docs/{kader}/index.md: De voorpagina van één specifiek kader"""
    md = f"""---
title: {s_info['label']}
parent: Begrippenkaders
permalink: /{s_info['slug']}/
---

# {s_info['label']}

{s_info['description']}

Gebruik de navigatie aan de linkerkant of de zoekbalk boven om begrippen te vinden.
"""
    with open(os.path.join(folder, "index.md"), "w", encoding="utf-8") as f:
        f.write(md)

def generate_markdown(g, s, info, concept_map, root_name):
    label = info['label']
    
    # Parent Logica:
    # 1. Is er een broader begrip? -> Dan is dat de parent.
    # 2. Geen broader? -> Dan is het ConceptScheme (root_name) de parent.
    parent_field = f"parent: {root_name}"
    if info['broader']:
        parent_field = f"parent: {info['broader'][0]}"

    # Front Matter
    md = f"""---
title: {label}
{parent_field}
permalink: {info['permalink']}
---

# {label}
""" 
    # --- INHOUD ---
    
    # 1. Definitie
    definition = g.value(s, SKOS.definition)
    if definition:
        md += f"\n## Definitie\n{definition}\n"
    else:
        md += f"\n## Definitie\n*Geen definitie beschikbaar.*\n"

    # 2. Toelichting
    scope_notes = list(g.objects(s, SKOS.scopeNote))
    if scope_notes:
        md += "\n## Toelichting\n"
        for note in scope_notes:
            md += f"{note}\n\n"

    # 3. Voorbeelden
    examples = list(g.objects(s, SKOS.example))
    if examples:
        md += "\n## Voorbeelden\n"
        for ex in examples:
            md += f"* {ex}\n"

    # 4. Terminologie Tabel
    alt_labels = [str(l) for l in g.objects(s, SKOS.altLabel)]
    hidden_labels = [str(l) for l in g.objects(s, SKOS.hiddenLabel)]
    
    if alt_labels or hidden_labels:
        md += "\n## Terminologie\n\n" # Dubbele newline voor tabel start
        md += "| Type | Term |\n| :--- | :--- |\n"
        md += f"| Voorkeursterm | {label} |\n"
        for alt in alt_labels:
            md += f"| Synoniem | {alt} |\n"
        for hidden in hidden_labels:
            md += f"| Zoekterm (verborgen) | {hidden} |\n"
        md += "\n" # Newline na tabel

    # 5. Relaties (Bullets, geen tabel)
    broader = get_internal_links(g, s, SKOS.broader, concept_map)
    narrower = get_internal_links(g, s, SKOS.narrower, concept_map)
    related = get_internal_links(g, s, SKOS.related, concept_map)

    if broader or narrower or related:
        md += "\n## Relaties\n"
        if broader: md += f"* **Bovenliggend:** {', '.join(broader)}\n"
        if narrower: md += f"* **Onderliggend:** {', '.join(narrower)}\n"
        if related:  md += f"* **Gerelateerd:** {', '.join(related)}\n"

    # 6. Externe verwijzingen
    see_also = get_external_links(g, s, RDFS.seeAlso)
    exact_match = get_external_links(g, s, SKOS.exactMatch)
    close_match = get_external_links(g, s, SKOS.closeMatch)

    if see_also or exact_match or close_match:
        md += "\n## Externe verwijzingen\n"
        for link in see_also: md += f"* **Zie ook:** {link}\n"
        for link in exact_match: md += f"* **Exacte overeenkomst:** {link}\n"
        for link in close_match: md += f"* **Nave overeenkomst:** {link}\n"

    # 7. Metadata Tabel
    sources = get_smart_sources(g, s)
    status = g.value(s, ADMS.status)
    modified = g.value(s, DCTERMS.modified) or g.value(s, PROV.generatedAtTime)
    editorial_note = g.value(s, SKOS.editorialNote)

    md += "\n## Metadata\n\n" # Dubbele newline voor tabel start
    md += "| Eigenschap | Waarde |\n| :--- | :--- |\n"
    
    if status:
        val = str(status).split('/')[-1].replace('-', ' ').title() if "http" in str(status) else str(status)
        md += f"| Status | {val} |\n"
    
    if sources:
        md += f"| Bron | {', '.join(sources)} |\n"
    
    if modified:
        md += f"| Datum wijziging | {modified} |\n"
        
    if editorial_note:
        md += f"| Redactionele notitie | {editorial_note} |\n"

    md += f"| URI | `{str(s)}` |\n"
    md += "\n" # Newline na tabel

    # Opslaan
    filename = f"{info['slug']}.md"
    with open(f"{OUTPUT_DIR}/{filename}", "w", encoding="utf-8") as f:
        f.write(md)

def get_internal_links(g, subject, predicate, concept_map):
    links = []
    for obj in g.objects(subject, predicate):
        uri = str(obj)
        if uri in concept_map:
            lbl = concept_map[uri]['label']
            permalink = concept_map[uri]['permalink']
            links.append(f"[{lbl}]({permalink})")
    return links

def get_external_links(g, subject, predicate):
    items = []
    for obj in g.objects(subject, predicate):
        if isinstance(obj, URIRef):
            url = str(obj)
            display = url
            # Simpele filters voor mooiere weergave
            if "wetten.overheid.nl" in url: display = "Wettenbank Overheid"
            if "eur-lex" in url: display = "Eur-Lex"
            items.append(f"[{display}]({url})")
        else:
            items.append(str(obj))
    return items

def get_smart_sources(g, subject):
    """
    Kijkt of de bron een Document-node is met een label en url (foaf:page),
    of gewoon een directe link/tekst.
    """
    items = []
    for obj in g.objects(subject, DCTERMS.source):
        # 1. Check: Is dit object gedefinieerd in onze eigen file?
        # We zoeken of dit object eigenschappen heeft in de graaf
        label = g.value(obj, RDFS.label)
        page = g.value(obj, FOAF.page)
        
        if page:
            # BINGO: Het is een referentie naar een Document node
            link_text = str(label) if label else "Bron"
            items.append(f"[{link_text}]({str(page)})")
        
        elif label:
            # Wel een label (bv. "Boek X"), maar geen URL
            items.append(str(label))
            
        else:
            # 2. Fallback: Het is geen node met properties, maar direct een URL of Tekst
            if isinstance(obj, URIRef):
                url = str(obj)
                # Oude logica voor directe links
                display = url
                if "wetten.overheid.nl" in url: display = "Wettenbank Overheid"
                items.append(f"[{display}]({url})")
            else:
                # Gewone tekst (Literal)
                items.append(str(obj))
                
    return items

if __name__ == "__main__":
    main()