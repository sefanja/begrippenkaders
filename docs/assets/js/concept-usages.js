document.addEventListener("DOMContentLoaded", async function() {
    const container = document.getElementById('concept-usages');
    const metaTag = document.querySelector('meta[name="concept-uri"]');
    
    // Stop als we niet op een begrippenpagina zijn
    if (!container || !metaTag) return;

    const currentUri = metaTag.getAttribute('content');
    // TODO: allow multiple and move to config
    const jsonPath = 'https://modellen.netbeheernederland.nl/stelsel/registers/concept_usages.json'; 

    try {
        const response = await fetch(jsonPath);
        if (!response.ok) throw new Error("JSON niet gevonden");
        
        const data = await response.json();
        
        // --- URI Normalisatie ---
        // Soms heeft de JSON een trailing slash en de meta-tag niet (of andersom)
        // We zoeken naar een exacte match OF een match met/zonder slash
        let usages = data[currentUri];
        
        if (!usages) {
            // Probeer alternatieven (met of zonder slash)
            const altUri = currentUri.endsWith('/') 
                ? currentUri.slice(0, -1) 
                : currentUri + '/';
            usages = data[altUri];
        }

        // Als er geen data is voor dit begrip, doen we niets (container blijft leeg)
        if (!usages || usages.length === 0) return;

        // --- Render HTML ---
        // We gebruiken de styling classes van Just the Docs
        let html = `
            <h2 id="gebruik-in-modellen">Gebruik</h2>
            <p>Dit begrip wordt toegepast in de volgende informatiemodellen:</p>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Model</th>
                            <th>Entiteit</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        usages.forEach(item => {
            // Check of er een specifieke URL is, anders fallback
            const linkUrl = item.url || '#';
            
            html += `
                <tr>
                    <td>
                        ${item.model}<br>
                    </td>
                    <td>
                        ${item.element} 
                        <span class="text-grey-lt-100 fs-2">(${item._type})</span>
                    </td>
                    <td>
                        <a href="${linkUrl}" target="_blank" class="btn btn-outline btn-sm fs-2">
                            Bekijk &rarr;
                        </a>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
            <p class="fs-2 text-grey-lt-100 mt-2">
                Deze informatie wordt automatisch opgehaald uit de actuele modeldefinities.
            </p>
        `;

        // Injecteer de HTML
        container.innerHTML = html;

    } catch (error) {
        console.warn("Kon model usages niet laden:", error);
    }
});
