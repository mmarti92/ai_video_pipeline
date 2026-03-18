# AI Video Pipeline

Automatically generates AI-powered stock-analysis videos by reading pending
jobs from a CockroachDB / PostgreSQL database table
(`pipeline_videos_stocks_ia`), producing an MP4 for each job, and writing
the result path back to the database.

---

## Architecture

```
main.py
 └─ pipeline.py           # orchestration loop
     ├─ database.py       # CockroachDB / PostgreSQL CRUD
     └─ video_generator.py
         ├─ OpenAI API    # AI-generated narration script (optional)
         ├─ gTTS          # text-to-speech audio
         ├─ matplotlib    # stock chart image
         └─ moviepy       # compose chart + audio → MP4
```

### Database table: `pipeline_videos_stocks_ia`

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `stock_symbol` | VARCHAR(10) | Ticker (e.g. `AAPL`) |
| `title` | VARCHAR(255) | Optional video title |
| `description` | TEXT | Optional extra context for the AI script |
| `status` | VARCHAR(20) | `pending` → `processing` → `completed` / `failed` |
| `output_path` | VARCHAR(500) | Path to the generated MP4 |
| `error_message` | TEXT | Populated on failure |
| `created_at` | TIMESTAMPTZ | Row creation time |
| `updated_at` | TIMESTAMPTZ | Last status change time |

---

## Quick start

### Option A — Docker (recommended)

#### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and set PG_CONNECTION_STRING (and optionally OPENAI_API_KEY)
```

#### 2. Build the image

```bash
make docker-build
# or: docker compose build
```

#### 3. Seed the database with sample stock symbols

```bash
make docker-seed
# or: docker compose --profile seed run --rm seed
```

#### 4. Run the pipeline (one batch)

```bash
make docker-run
# or: docker compose run --rm pipeline
```

#### 5. Run continuously (long-running service)

```bash
make docker-continuous
# or: docker compose --profile continuous up -d pipeline-continuous
```

---

### Option B — Local Python

#### 1. Install dependencies

```bash
make install
# or: pip install -r requirements.txt
```

#### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set PG_CONNECTION_STRING (and optionally OPENAI_API_KEY)
```

#### 3. Seed the database

```bash
make seed
# or: python seed_stocks.py
# Custom symbols: python seed_stocks.py --symbols AAPL MSFT NVDA
```

#### 4. Run the pipeline (one batch)

```bash
make run
# or: python main.py
```

#### 5. Run continuously (polls for new jobs every 60 s)

```bash
make run-continuous
# or: python main.py --continuous
```

#### 6. Insert a single test job

```bash
python main.py --seed AAPL "Apple Inc. Weekly Analysis"
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PG_CONNECTION_STRING` | ✅ | — | Full PostgreSQL/CockroachDB DSN |
| `OPENAI_API_KEY` | ❌ | — | Enables AI-generated scripts |
| `OUTPUT_DIR` | ❌ | `./output` | Directory for generated MP4 files |
| `PIPELINE_BATCH_SIZE` | ❌ | `10` | Jobs processed per run |
| `PIPELINE_POLL_INTERVAL_SECONDS` | ❌ | `60` | Sleep between batches (continuous mode) |

---

## Database migration

Applied automatically on startup. To apply manually:

```bash
psql "$PG_CONNECTION_STRING" -f migrations/001_create_pipeline_videos_stocks_ia.sql
```

---

## Tests

```bash
make test
# or: pytest tests/
```