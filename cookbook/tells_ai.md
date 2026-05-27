# tells_ai.md — Biblioteca de patrones AI con severidad

Patrones que delatan output LLM. Cada uno con severidad declarada para evitar reportes ruidosos o silentes.

**Severidades:**
- **BLOCK**: alta probabilidad de delatar AI. Pisar siempre.
- **WARN**: contexto importa. Reportar y dejar al autor decidir.
- **INFO**: heuristica de baja confianza. Solo informativa.

---

## BLOCK — pisar siempre

### Frases-slogan "X is not Y, it's Z" / "No es A, es B"

Patron: una construccion retorica que opone dos cosas con misma estructura sintactica para terminar con la "verdad reveladora".

| Patron regex aproximado | Ejemplos |
|---|---|
| `\b(is not\|isn't\|no es\|no son)\s+.{2,40}\s*[,.]\s*(it's\|es)\s+` | "It's not about precision, it's about confidence." / "La ingenieria no es X, es Y." |
| `\bnot just\s+.{2,40}\s+but\b` | "Not just a tool, but a philosophy." |

Reemplazo sugerido: oracion afirmativa directa sin contraste retorico.

### Aforismos de cierre

Patron: la ultima oracion del texto es una frase corta, sentenciosa, atemporal, tipo "lesson learned".

| Subpatron | Ejemplos |
|---|---|
| Cierre absoluto | "It always has." / "Siempre fue asi." / "And that's the point." |
| Verdad universal | "Engineering is about decisions." / "El criterio es todo." |
| Imperativo abstracto | "Verify before you trust." / "Confiar despues de verificar." |

Reemplazo sugerido: cierre con dato concreto, resultado pragmatico, o pregunta abierta sin punchline.

### Tripartitas paralelas (≥2 en mismo parrafo)

Patron: tres clausulas con misma estructura sintactica como recurso retorico.

| Ejemplo |
|---|
| "Fast. Reliable. Predictable." |
| "We design. We measure. We deliver." |
| "X happens. Y happens. Z happens." |

Una tripartita aislada puede ser estilo. Dos en mismo parrafo es delator.

Reemplazo sugerido: variar la estructura de las clausulas. Una larga + una corta + una intermedia.

### Firma corporativa al pie

Patron: el texto cierra con la marca repetida o un tagline.

| Ejemplo |
|---|
| "Asi trabaja DG." |
| "DG Ingenieria — Infraestructura Inteligente." |
| "Built with care. Backed by data." |

Reemplazo sugerido: el cierre es la ultima idea del cuerpo. La plataforma ya muestra el nombre arriba.

### Comparaciones con competencia / negaciones de identidad

Patron: definirse por lo que no se es / no se hace / lo que otros hacen mal.

| Patron regex aproximado |
|---|
| `\bno\s+(es\|somos\|hacemos\|ejecutamos)\b` |
| `\b(a diferencia de\|unlike\|whereas)\b` |
| `lo que (X )?no\b` |
| `\bsin\s+(teatro\|bombo\|excepciones\|promesas)\b` |

Reemplazo sugerido: describir lo que SI se hace. El cerebro procesa "no pienses en un elefante" como "piensa en un elefante".

### Frases-patron LLM HN/Reddit/X

Patron: locuciones de relleno que aparecen estadisticamente sobre-representadas en output LLM.

| Frase | Notas |
|---|---|
| "worth noting" | clasico LLM-ism HN |
| "the X framing is the right one" | LLM hedge |
| "matters for a specific failure mode" | LLM tech-blog |
| "different layer of the pipeline" | LLM tech-explainer |
| "let's dive in / let's break it down" | LLM intro |
| "in essence / fundamentally / at its core" | LLM transicion |
| "this is more than just X" | LLM build-up |
| "imagine if / imagine that / imagine X" | LLM hook retorico |
| "what if I told you" | LLM hook clickbait |
| "the future of X is here" | LLM cierre profetico |

Reemplazo sugerido: cortar la frase, ir directo al contenido.

---

## WARN — contexto importa

### Em-dash `—`

Uso valido: ingles formal en blog largo, ensayistico.
Uso delator: comments HN/Reddit/X, posts LinkedIn cortos, replies. La punctuacion natural en informal es coma, parentesis, o punto.

Excepcion: si el perfil declara `tells personales a preservar: em-dash` (autor que lo usa de forma autentica), no flaggear.

### Falta de contracciones coloquiales

En EN: `do not / cannot / it is / I am / will not` en contexto informal delata LLM. La voz humana en chat-style usa `don't / can't / it's / I'm / won't`.

En ES: menos relevante (espanol no contrae igual).

Excepcion: registro formal (paper, propuesta) — no flaggear.

### Ritmo demasiado uniforme

Patron: parrafos de longitud parecida, oraciones de largo similar, sin variacion.

Heuristica: si stdev del largo de oraciones (palabras) < 4, flag WARN.

Reemplazo sugerido: insertar una oracion corta o un fragmento.

### Revelacion-de-cierre / punchline

Patron: el ultimo parrafo "revela" la moraleja con tono enfatico.

Ejemplos:
- "And that's when I realized..."
- "The lesson? ..."
- "Turns out..."

Reemplazo sugerido: terminar plano, sin moraleja. El lector saca su propia conclusion.

---

## INFO — heuristica de baja confianza

### Cifras estimativas sin respaldo

Patron: numero grande sin fuente verificable.

| Ejemplo flag | Aceptable |
|---|---|
| "miles de millones perdidos en obras mal disenadas" | "5,000 m3 de relleno extra en el proyecto X" |
| "cientos de miles de dolares de sobrecostes" | "$100 arithmetic bug" (chiquito, verificable) |

Reemplazo sugerido: cifra concreta con fuente, o expresion cualitativa sin numero ("mas relleno", "margen conservador").

### "I/my" sugiriendo unipersonalidad

Patron: primera persona singular usada para hablar de trabajo de equipo o capacidad ejecutiva.

| Flag | Mejor |
|---|---|
| "I built a 4800-line platform" | "We built a 4800-line platform" |
| "A QA agent in my workflow" | "A QA agent in our workflow" |

Excepcion: introspeccion personal (decision, pensamiento, experiencia individual) → "I" es correcto.

| Excepcion | Ejemplo |
|---|---|
| Pensamiento | "What I learned from this..." |
| Decision personal | "I decided to defer the merge" |
| Experiencia individual | "It took me three sessions to see it" |

### Verbos imprecisos

Heuristica: si el draft usa "redisenar" en contexto sin diseno previo, "optimizar" sin metrica, "transformar" sin ejes — flag INFO.

### Claims universales sin respaldo

Patron: afirmaciones tipo "nobody X" / "everybody Y" / "most engineers Z" / "few people W" sin fuente verificable. Generalizaciones que suenan autoritativas pero son indemostrables.

| Patron regex aproximado | Ejemplos |
|---|---|
| `\b(nobody\|everybody\|everyone\|no one)\b` | "nobody audits", "everybody knows" |
| `\b(nadie\|todos\|todo el mundo)\b` | "nadie audita", "todos saben" |
| `\b(most\|few)\s+(engineers\|developers\|companies\|people)\b` | "most engineers just sign off", "few actually verify" |
| `\b(la mayoria\|pocos)\s+(de\s+los\s+)?(ingenieros\|empresas)\b` | "la mayoria de los ingenieros" |

Severidad subida a **BLOCK** si el claim ademas pone en mal lugar al gremio (cicatriz 8).

Reemplazo sugerido: dato concreto con fuente, o eliminar el claim si no se puede respaldar.

---

## Patrones de severidad por canal (override del default)

Algunos patrones cambian severidad segun canal:

| Patron | LinkedIn DG | LinkedIn Victor | X | HN comment | Blog largo |
|---|---|---|---|---|---|
| Em-dash | WARN | WARN | BLOCK | BLOCK | INFO |
| Tripartita 1x | INFO | WARN | WARN | BLOCK | INFO |
| Aforismo cierre | BLOCK | BLOCK | BLOCK | BLOCK | WARN |
| "I built" alone | INFO | INFO | BLOCK | INFO | INFO |
| Contraccion missing | n/a | n/a | WARN | BLOCK | INFO |

El perfil del canal puede sobreescribir esta tabla declarando `severity_overrides:` en el bloque del canal.

---

## Calibracion

La biblioteca arranca con estos defaults basados en cicatrices Victor (canal Victor LinkedIn + HN comments). Para otros autores:
1. Cargar 3-5 drafts del autor que ya publico con buen recibimiento.
2. Correr la skill en modo dry-run sobre esos.
3. Si genera muchos falsos positivos en un patron, bajar severidad o agregarlo a "tells personales a preservar" del perfil.
4. Si deja pasar patrones que el autor identifica como AI, agregar al `tells_ai.md` local.

`tells_ai.md` es libreria base. El perfil del autor puede extenderla via `extra_tells:` declarando patrones adicionales.
