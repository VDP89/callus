# Voice Profile — Template

Copiar este archivo a `voice-profile.md` (en cwd o en `.claude/voice-profiles/<name>.md`) y completar cada seccion. Borrar las secciones de instrucciones.

---

## Identidad

- **Nombre del autor:** {nombre publico, como aparece en el canal}
- **Rol declarado:** {ej. "Gerente General DG Ingenieria SRL" — NUNCA inventar titulos}
- **Cuentas canonicas:** {LinkedIn URL, X handle, blog URL — para auto-detect de hint `# canal:`}

## Voz general (aplica a todos los canales)

- **Persona narrativa:** primera persona experiencial / corporativa sobria / observador / hibrida
- **Hook style preferido:** situacional pasado concreto / presente atemporal / pregunta retorica / dato fuerte
- **Framing:** positivo estricto (sin "no es X") / mixto con justificacion / sin restriccion
- **Tells personales a preservar:** {lista de patrones que en otros serian AI-ism pero son voz real del autor — ej. "habian" coloquial, typos menores intencionales}
- **Vocabulario prohibido:** {palabras/frases que el autor no usa nunca — ej. "leverage", "unlock", "engineering excellence"}
- **Cifras:** solo verificables / estimativas OK con disclaimer / sin restriccion

## Canales

Repetir bloque por canal. El hint `# canal: <name>` en el draft selecciona el bloque.

### Canal: linkedin-{nombre}

- **Audiencia primaria:** {ej. "decisores construccion LATAM, 57% perfil decisor"}
- **Largo target:** {min}-{max} palabras (ej. 150-280)
- **Distribucion de largos:** {ej. "60% medio, 25% corto, 15% largo"}
- **Hashtags canonicos:** {lista 3-5 hashtags reales con ≥1000 seguidores LinkedIn — sin frase-slug}
  - Pool tecnico: `#x #y #z`
  - Pool sector: `#a #b`
  - Pool herramienta: `#p #q`
- **Hashtags por post:** 3-5
- **Link funnel destino default:** {URL pagina/insight web — null si no aplica}
- **Excepcion sin link:** maximo 20% posts/mes (declarar en draft con `# excepcion-funnel`)
- **Idioma:** ES / EN / bilingue por tema
- **Voz especifica del canal:** {1ra persona experiencial / corporativa / otra}

### Canal: x-{nombre}

- **Audiencia primaria:** {ej. "AI builders global, devs"}
- **Largo target:** {chars} (ej. 200-280 para tweet, threads aparte)
- **Idioma:** EN posts originales / ES quote-replies LATAM / bilingue por thread
- **Tells personales a preservar:** {ej. "lowercase ocasional", "contracciones forzadas"}
- **Vocabulario prohibido en X:** {ej. "1 engineer / alone", "building alone" — cicatriz 13}
- **Link funnel destino:** {URL blog / repo}

### Canal: blog-{nombre}

- **Audiencia:** {especifica del blog}
- **Largo target:** {min}-{max} palabras
- **Voz:** primera persona ensayistica / explicacion tecnica / hibrida
- **Estructura preferida:** {ej. "hook + 3 secciones + cierre pragmatico"}

### Canal: hn-comment / reddit-comment

- **Regla operativa:** Author escribe, Claude ajusta minimo. NO drafts completos salvo pedido explicito.
- **Largo:** 2-4 lineas, una sola idea
- **Tells a evitar especificos comunidad tech:**
  - em-dashes
  - aforismos de cierre tipo "It always has"
  - estructuras tripartitas paralelas
  - frases-patron LLM ("worth noting", "the X framing is right one")
  - sin contracciones coloquiales (don't, I'm, it's)
  - ritmo demasiado calibrado
- **Typos organicos:** preservar si el autor los deja (textura humana)

## Reglas globales del autor

(Cicatrices personales que no se piden por canal sino que aplican siempre)

1. {ej. "Nunca compararse con competidores"}
2. {ej. "Nunca decir lo que NO se hace — solo lo que SI se hace"}
3. {ej. "Cifras estimativas infladas: prohibido"}
4. ...

## Glosario de hooks aprobados (opcional)

Lista de aperturas que ya funcionaron para este autor — para calibrar el detector de "hook desvio":

- "Ante un dato tecnico que no cerraba, habian dos caminos..." (situacional pasado)
- "Certidumbre desde las bases" (titular sin verbo, OK como subtitulo)
- ...

## Notas operativas

- Verificar hashtags ≥1000 seguidores antes de incorporar al pool.
- Editar este perfil inline cuando aparece cicatriz nueva del autor. No versionar fancy.
- Si un canal nuevo aparece (ej. threads, mastodon), agregar bloque aca.
