# Pipeline: Videos Automatizados de Stock Predictions con IA

> Guía completa para generar y distribuir videos diarios de predicciones de acciones usando tu API fintech + IA

---

## Índice

1. [Visión general del sistema](#1-visión-general-del-sistema)
2. [Stack de herramientas](#2-stack-de-herramientas)
3. [Presupuesto mensual](#3-presupuesto-mensual)
4. [Estrategia de contenido](#4-estrategia-de-contenido)
5. [Pipeline paso a paso](#5-pipeline-paso-a-paso)
6. [Prompt maestro para Claude API](#6-prompt-maestro-para-claude-api)
7. [Configuración de Make.com](#7-configuración-de-makecom)
8. [Producción de video](#8-producción-de-video)
9. [Distribución en redes sociales](#9-distribución-en-redes-sociales)
10. [Compliance y disclaimers legales](#10-compliance-y-disclaimers-legales)
11. [Log y seguimiento](#11-log-y-seguimiento)
12. [Hoja de ruta por fases](#12-hoja-de-ruta-por-fases)

---

## 1. Visión general del sistema

El sistema convierte automáticamente los expected returns de tu API fintech en videos cortos publicados diariamente en Instagram, TikTok, YouTube y X/Twitter — en español e inglés — sin intervención manual.

```
Tu API fintech (5.000+ stocks)
        ↓
   Filtro lista blanca (~150 tickers populares)
        ↓
   Top pick del día (mayor expected return 1 mes)
        ↓
   Claude API → guión ES + EN + captions + hashtags
        ↓
   ElevenLabs → audio ES + audio EN
        ↓
   HeyGen → video con avatar y lip-sync
        ↓
   Creatomate → formatos 9:16 y 1:1 + subtítulos
        ↓
   Buffer → publicación en 4 redes sociales
        ↓
   Google Sheets → log diario de ejecución
```

**Frecuencia:** Lunes a viernes, 09:45 AM ET (15 min tras apertura NYSE)  
**Output diario:** 4 videos (2 idiomas × 2 formatos)  
**Output semanal:** 1 video largo en YouTube con top picks por sector

---

## 2. Stack de herramientas

| Herramienta | Función | Categoría |
|---|---|---|
| **Tu API fintech** | Expected returns 1m y 3m sobre 5.000+ acciones | Datos |
| **Make.com** | Orquestador principal del pipeline | Automatización |
| **Claude API** | Generación de guiones, captions y hashtags | IA / Contenido |
| **ElevenLabs** | Text-to-speech profesional (ES + EN) | Audio |
| **HeyGen** | Avatar presentador con lip-sync | Video |
| **Creatomate** | Templates, subtítulos y formatos por red | Edición |
| **Buffer** | Scheduling y publicación en redes sociales | Distribución |
| **Google Sheets** | Lista blanca de tickers + log de ejecuciones | Control |
| **Google Drive** | Almacenamiento de audios y videos intermedios | Storage |

---

## 3. Presupuesto mensual

| Herramienta | Plan | Costo/mes |
|---|---|---|
| Polygon.io | Starter | $29 |
| Claude API (Sonnet) | Pay-per-use (~$0.01/video) | ~$40 |
| ElevenLabs | Creator | $22 |
| HeyGen | Creator | $29 |
| CapCut Pro / Creatomate | Pro | $8–$29 |
| Make.com | Core | $29 |
| Buffer | Essentials | $18 |
| **Total estimado** | | **~$175–$196/mes** |
| **Margen disponible** | (sobre $500) | **~$300+/mes** |

---

## 4. Estrategia de contenido

### Videos cortos diarios (25 segundos)
- **1 stock por video** — el top pick del día de tu modelo
- **Selección:** mayor expected return a 1 mes dentro de la lista blanca de tickers populares
- **Idiomas:** español e inglés (2 versiones del mismo video)
- **Formatos:** 9:16 (TikTok, Reels, YouTube Shorts) y 1:1 (X/Twitter)
- **Publicación:** misma mañana, tras apertura de mercado

### Video largo semanal (YouTube)
- **Top picks por sector** — mejor pick de Tech, Salud, Energía, Finanzas, Consumo
- **Duración:** 5-8 minutos
- **Publicación:** viernes tarde o lunes por la mañana
- **Estructura:** intro del modelo → 5 picks con contexto → disclaimer

### Lista blanca de tickers populares
Mantén un Google Sheet con ~150 tickers de alta notoriedad entre el público retail:

```
AAPL, NVDA, TSLA, META, AMZN, MSFT, GOOGL, AMD, NFLX, JPM,
BABA, COIN, PLTR, RIVN, LCID, GME, AMC, DIS, UBER, LYFT,
SOFI, HOOD, PYPL, SQ, SHOP, SNAP, PINS, TWLO, ZM, DKNG,
SPY, QQQ, ARKK, GLD, SLV, BTC-USD, ETH-USD...
```

> Esta lista se actualiza manualmente cuando aparecen nuevos tickers virales. Se gestiona desde Google Sheets y Make.com la lee automáticamente al inicio de cada ejecución.

---

## 5. Pipeline paso a paso

### Paso T — Trigger diario
- **Módulo Make.com:** `Schedule`
- **Hora:** `09:45 AM ET`
- **Días:** lunes a viernes
- **Timezone:** `America/New_York`

---

### Paso 1 — Llamada a tu API fintech
- **Módulo Make.com:** `HTTP → Make a request`
- **Method:** `GET`
- **URL:** tu endpoint de expected returns
- **Headers:** `Authorization: Bearer {TU_API_KEY}`
- **Output:** array JSON con los 5.000+ stocks

**Estructura esperada del JSON de tu API:**
```json
[
  {
    "ticker": "NVDA",
    "company_name": "NVIDIA Corporation",
    "current_price": 127.45,
    "price_target": 142.00,
    "expected_return_1m": 11.4,
    "expected_return_3m": 24.7
  },
  ...
]
```

---

### Paso 2 — Filtrar por lista blanca
- **Módulo Make.com:** `Google Sheets → Get rows` + `Array aggregator` + `Filter`
- Lee la lista blanca desde Google Sheets
- Filtra el array de tu API para quedarse solo con tickers de la lista
- **Output:** subarray de ~100-150 stocks populares con sus expected returns

---

### Paso 3 — Seleccionar el top pick del día
- **Módulo Make.com:** `Array aggregator → Sort + First item`
- Ordena por `expected_return_1m` descendente
- Extrae el primer elemento
- **Variables resultantes:**

| Variable Make.com | Campo de tu API |
|---|---|
| `{{ticker}}` | `ticker` |
| `{{company_name}}` | `company_name` |
| `{{current_price}}` | `current_price` |
| `{{price_target}}` | `price_target` |
| `{{return_1m}}` | `expected_return_1m` |
| `{{return_3m}}` | `expected_return_3m` |
| `{{date}}` | fecha actual (módulo Date) |

---

### Paso 4 — Generar guión con Claude API
- **Módulo Make.com:** `HTTP → Make a request`
- **URL:** `https://api.anthropic.com/v1/messages`
- **Method:** `POST`
- **Headers:**
  ```
  x-api-key: {TU_CLAUDE_API_KEY}
  anthropic-version: 2023-06-01
  content-type: application/json
  ```
- Parsea la respuesta con `JSON → Parse JSON`
- **Output:** `script_es`, `script_en`, `caption_es`, `caption_en`, `hashtags_es`, `hashtags_en`

> Ver sección 6 para el prompt completo.

---

### Paso 5 — Generar audio con ElevenLabs
- **Módulo Make.com:** `HTTP → Make a request` (×2, en paralelo)
- **URL:** `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
- **Llamada A:** `script_es` → voz española → `audio_es.mp3`
- **Llamada B:** `script_en` → voz inglesa → `audio_en.mp3`
- Sube ambos archivos a Google Drive

**Configuración de voz recomendada:**
```json
{
  "text": "{{script_es}}",
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.75,
    "similarity_boost": 0.85,
    "style": 0.3,
    "use_speaker_boost": true
  }
}
```

---

### Paso 6 — Crear video con HeyGen
- **Módulo Make.com:** `HTTP → Make a request` (×2)
- **URL:** `https://api.heygen.com/v2/video/generate`
- **Input:** template_id fijo + audio de ElevenLabs
- **Output:** `video_id`

**Polling para esperar el render:**
- Módulo: `HTTP → Make a request` a `GET /v1/video_status.get?video_id={{video_id}}`
- Repite cada 30 segundos hasta que `status === "completed"`
- Descarga la URL del video final y guarda en Google Drive

> ⚠️ El render de HeyGen toma ~2-3 minutos por video. Es el paso más lento del pipeline.

---

### Paso 7 — Añadir subtítulos y adaptar formatos
- **Herramienta:** Creatomate (tiene módulo nativo en Make.com)
- **Templates a crear en Creatomate:**
  - `template_9_16`: 9:16 con subtítulos animados + logo
  - `template_1_1`: 1:1 con ticker y datos superpuestos

**Por cada idioma, genera 2 formatos:**
```
video_es_9_16.mp4  → Instagram Reels + TikTok + YouTube Shorts
video_es_1_1.mp4   → X/Twitter (versión española)
video_en_9_16.mp4  → TikTok EN + YouTube Shorts EN
video_en_1_1.mp4   → X/Twitter (versión inglesa)
```

---

### Paso 8 — Publicar en redes sociales
- **Módulo Make.com:** `Buffer → Create update` (×4)

| Red | Video | Caption | Idioma |
|---|---|---|---|
| Instagram Reels | 9:16 | `caption_es` + `hashtags_es` | ES |
| TikTok | 9:16 | `caption_en` + `hashtags_en` | EN |
| YouTube Shorts | 9:16 | título generado por Claude | EN |
| X / Twitter | 1:1 | caption ≤280 chars | EN |

---

### Paso 9 — Log en Google Sheets
- **Módulo Make.com:** `Google Sheets → Add a row`

**Columnas del log:**
```
fecha | ticker | return_1m | return_3m | precio_actual | precio_target | 
estado | link_ig | link_tiktok | link_yt | link_twitter | notas
```

> En 3 meses tendrás un dataset real para validar públicamente la precisión de tu modelo. Es un activo de credibilidad enorme.

---

## 6. Prompt maestro para Claude API

### System prompt (fijo — configurar una vez)

```
You are a financial content writer for a retail investment audience. Your job is to write short video scripts (25 seconds when read aloud at a natural pace = ~65 words) based on quantitative stock predictions from a fintech model.

Rules:
- Tone: confident, clear, energetic. Like a smart friend explaining a trade idea.
- Never use jargon. Translate everything to plain language.
- Always end with a legal disclaimer (1 short sentence).
- Never guarantee returns. Use language like "our model projects", "expected return", "signals suggest".
- Output ONLY valid JSON. No markdown, no explanation, no extra text.
```

### User prompt (dinámico — Make.com inyecta las variables)

```
Generate two 25-second video scripts (Spanish and English) for this stock prediction:

STOCK DATA:
- Ticker: {{ticker}}
- Company name: {{company_name}}
- Current price: ${{current_price}}
- Price target: ${{price_target}}
- Expected return 1 month: {{return_1m}}%
- Expected return 3 months: {{return_3m}}%
- Date: {{date}}

SCRIPT STRUCTURE (follow exactly):
1. Hook (1 sentence): Grab attention with the opportunity
2. The signal (2 sentences): What the model sees, the numbers
3. The target (1 sentence): Where price could go
4. CTA (1 sentence): Follow for daily picks
5. Disclaimer (1 sentence): Not financial advice

OUTPUT FORMAT (JSON only):
{
  "ticker": "{{ticker}}",
  "date": "{{date}}",
  "script_es": "...",
  "script_en": "...",
  "caption_es": "...",
  "caption_en": "...",
  "hashtags_es": ["...", "..."],
  "hashtags_en": ["...", "..."],
  "youtube_title_en": "..."
}
```

### Ejemplo de output esperado

```json
{
  "ticker": "NVDA",
  "date": "2026-03-17",
  "script_es": "NVIDIA está en nuestro radar hoy. Nuestro modelo proyecta un retorno esperado del 12% en el próximo mes, con un precio objetivo de $142. Las señales cuantitativas apuntan a momentum alcista en semiconductores. El precio actual de $127 podría ser una entrada interesante. Síguenos para los top picks diarios. Esto no es asesoramiento financiero — haz siempre tu propia investigación.",
  "script_en": "NVIDIA is on our radar today. Our model projects a 12% expected return over the next month, with a price target of $142. Quantitative signals point to strong bullish momentum in semiconductors. At $127, this could be a compelling entry. Follow us for daily top picks. This is not financial advice — always do your own research.",
  "caption_es": "NVDA en nuestro radar hoy 🎯 Retorno esperado +12% en 30 días según nuestro modelo cuantitativo. ¿Lo tienes en cartera?",
  "caption_en": "NVDA on our radar today 🎯 Our quant model projects +12% expected return in 30 days. Is it in your portfolio?",
  "hashtags_es": ["#NVDA", "#Inversiones", "#AccionesHoy", "#StockPicks", "#MercadosFinancieros"],
  "hashtags_en": ["#NVDA", "#StockPicks", "#Investing", "#QuantFinance", "#StockMarket"],
  "youtube_title_en": "NVDA: +12% Expected Return in 30 Days | Daily Stock Pick"
}
```

---

## 7. Configuración de Make.com

### Estructura de escenarios recomendada

Crea **2 escenarios separados** en Make.com:

**Escenario A — Pipeline diario (shorts)**
```
Schedule → HTTP (tu API) → Google Sheets (lista blanca) → 
Filter → Sort → HTTP (Claude) → Parse JSON → 
HTTP (ElevenLabs ×2) → HTTP (HeyGen ×2) → 
Creatomate (×4 formatos) → Buffer (×4 redes) → 
Google Sheets (log)
```

**Escenario B — Video largo semanal**
```
Schedule (viernes 12PM) → HTTP (tu API) → 
Filtro por sector (×5) → HTTP (Claude, prompt largo) → 
ElevenLabs → HeyGen → Creatomate → YouTube upload → 
Google Sheets (log)
```

### Variables de entorno en Make.com
Guárdalas en `Tools → Variables` para no exponerlas en los módulos:

```
FINTECH_API_KEY=...
CLAUDE_API_KEY=...
ELEVENLABS_API_KEY=...
HEYGEN_API_KEY=...
CREATOMATE_API_KEY=...
BUFFER_ACCESS_TOKEN=...
WHITELIST_SHEET_ID=...
LOG_SHEET_ID=...
```

### Gestión de errores
- Activa `Error handling` en Make.com para cada módulo HTTP crítico
- Configura un módulo `Email` o `Slack` al final para notificarte si el escenario falla
- Guarda el error en el log de Google Sheets con estado `ERROR`

---

## 8. Producción de video

### Configuración de HeyGen

1. Crea tu avatar personalizado en HeyGen (tarda ~24h en procesarse)
2. Diseña el template de video en HeyGen Studio:
   - Fondo: pantalla de datos financieros o abstracto de tu marca
   - Lower third: ticker + expected return superpuesto
   - Logo en esquina superior
3. Anota el `template_id` — es lo que pasa Make.com en cada llamada

### Configuración de ElevenLabs

- **Voz española recomendada:** "Mateo" o crea una voz clonada de tu propio equipo
- **Voz inglesa recomendada:** "Adam" o "Antoni"
- Mantén `stability: 0.75` para sonar natural sin robótico

### Configuración de Creatomate

Crea 2 templates en Creatomate:

**Template 9:16 (TikTok / Reels / YouTube Shorts)**
- Resolución: 1080×1920
- Elementos dinámicos: `{{video_heygen}}`, `{{subtitulos}}`, `{{ticker}}`, `{{return_1m}}`
- Subtítulos: fuente grande, alta legibilidad, con highlight de palabra activa

**Template 1:1 (X / Twitter)**
- Resolución: 1080×1080
- Mismos elementos, layout centrado

---

## 9. Distribución en redes sociales

### Horarios óptimos de publicación por red

| Red | Hora recomendada | Zona horaria |
|---|---|---|
| TikTok | 10:00 AM | ET |
| Instagram Reels | 11:00 AM | ET |
| YouTube Shorts | 12:00 PM | ET |
| X / Twitter | 09:30 AM | ET (apertura mercado) |

### Estrategia de hashtags

**Español (Instagram / TikTok ES):**
```
#Inversiones #AccionesHoy #StockPicks #BolsaDeValores 
#MercadosFinancieros #InteligenciaArtificial #FinanzasPersonales
#{{TICKER}}
```

**Inglés (TikTok EN / YouTube / Twitter):**
```
#StockPicks #Investing #QuantFinance #StockMarket 
#AIInvesting #DailyPicks #FinTech #{{TICKER}}
```

---

## 10. Compliance y disclaimers legales

> ⚠️ Este es el punto más crítico del proyecto. Los videos de predicciones financieras están regulados en la mayoría de jurisdicciones.

### Disclaimer obligatorio en cada video

**Español:**
> "Este contenido es solo informativo y no constituye asesoramiento financiero. Las predicciones son generadas por un modelo cuantitativo y no garantizan resultados futuros. Invierte siempre con responsabilidad."

**Inglés:**
> "This content is for informational purposes only and does not constitute financial advice. Predictions are generated by a quantitative model and do not guarantee future results. Always invest responsibly."

### Checklist de compliance por plataforma

- [ ] Disclaimer en los primeros 5 segundos del video O en el caption
- [ ] Nunca usar "garantizado", "seguro", "100%", "sin riesgo"
- [ ] Siempre usar lenguaje condicional: "nuestro modelo proyecta", "señales sugieren"
- [ ] Incluir en el perfil de cada red: "No somos asesores financieros registrados"
- [ ] YouTube: activar categoría "Finanzas" y revisar políticas de contenido financiero
- [ ] TikTok: revisar políticas de contenido financiero (especialmente en US)

### Aviso legal adicional para Instagram bio / YouTube About:
```
Las predicciones mostradas son generadas por modelos cuantitativos 
con fines educativos e informativos únicamente. No somos asesores 
financieros registrados. Consulta siempre a un profesional antes 
de invertir. Rentabilidades pasadas no garantizan resultados futuros.
```

---

## 11. Log y seguimiento

### Estructura del Google Sheet de control

**Hoja 1: Log diario**

| Columna | Descripción |
|---|---|
| `fecha` | Fecha de ejecución |
| `ticker` | Stock cubierto |
| `return_1m_predicho` | Expected return al momento de publicar |
| `return_3m_predicho` | Expected return 3 meses |
| `precio_publicacion` | Precio del stock al publicar |
| `precio_target` | Precio objetivo del modelo |
| `estado` | OK / ERROR |
| `link_instagram` | URL del post |
| `link_tiktok` | URL del post |
| `link_youtube` | URL del post |
| `link_twitter` | URL del post |
| `notas` | Incidencias o ajustes manuales |

**Hoja 2: Performance tracking (actualizar mensualmente)**

| Columna | Descripción |
|---|---|
| `ticker` | Stock |
| `fecha_publicacion` | Cuándo se publicó |
| `precio_publicacion` | Precio al publicar |
| `precio_1m` | Precio real 1 mes después |
| `retorno_real_1m` | Retorno real vs predicho |
| `acierto` | SÍ / NO (si el modelo fue correcto en dirección) |

> Este tracking de performance es un activo de credibilidad enorme. En 6 meses puedes publicar "nuestro modelo acertó el X% de las predicciones" con datos verificables.

---

## 12. Hoja de ruta por fases

### Fase 1 — Semanas 1-2: Infraestructura
- [ ] Crear cuenta en Make.com, Claude API, ElevenLabs, HeyGen, Creatomate, Buffer
- [ ] Configurar Google Drive y Google Sheets (lista blanca + log)
- [ ] Armar lista blanca de ~150 tickers populares
- [ ] Validar conexión de tu API en Make.com (pasos 1-3)
- [ ] Validar output de Claude API con datos reales (paso 4)

### Fase 2 — Semana 3: Producción
- [ ] Crear avatar en HeyGen y esperar aprobación
- [ ] Diseñar templates en Creatomate (9:16 y 1:1)
- [ ] Configurar voces en ElevenLabs
- [ ] Primer video de prueba end-to-end (sin publicar)

### Fase 3 — Semana 4: Lanzamiento
- [ ] Test completo del pipeline en modo manual
- [ ] Primer video publicado en 1 red (Instagram)
- [ ] Ajuste de prompt, voces y templates según resultado
- [ ] Activar pipeline completo en las 4 redes

### Fase 4 — Mes 2-3: Optimización
- [ ] Añadir video largo semanal (YouTube)
- [ ] A/B test de captions (español vs inglés, engagement)
- [ ] Añadir versión en portugués si hay audiencia brasileña
- [ ] Primera publicación de "accuracy report" del modelo

### Fase 5 — Mes 4+: Monetización
- [ ] Lanzar newsletter de pago con picks extendidos
- [ ] Añadir CTA a página web o plataforma de tu fintech
- [ ] Explorar colaboraciones con cuentas de finanzas personales
- [ ] Considerar modelo de suscripción para picks premium

---

## Recursos y documentación

| Recurso | URL |
|---|---|
| Claude API docs | https://docs.anthropic.com |
| ElevenLabs API | https://docs.elevenlabs.io |
| HeyGen API | https://docs.heygen.com |
| Creatomate API | https://creatomate.com/docs |
| Make.com Help | https://www.make.com/en/help |
| Buffer API | https://buffer.com/developers/api |
| Polygon.io docs | https://polygon.io/docs |

---

*Documento generado el 17 de marzo de 2026 · Actualizar según evolución de herramientas y plataformas*
