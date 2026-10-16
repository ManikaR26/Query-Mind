# QueryMind — Schema-Aware Text-to-SQL Analytics Copilot

QueryMind converts a natural-language question into a safe MySQL query using a fine-tuned FLAN-T5 model, executes the read-only query against Spider databases migrated to MySQL, and displays the result in a Streamlit dashboard.

## Why this version is credible

- **Public benchmark:** Spider 1.0, not a custom fake training dataset.
- **Real model training:** PyTorch + FLAN-T5 sequence-to-sequence fine-tuning.
- **Schema-aware generation:** each model input contains the selected database schema and relationships.
- **MySQL application layer:** Spider SQLite databases can be migrated to MySQL; the app queries MySQL.
- **Safety layer:** only read-only SELECT/CTE queries are allowed.
- **Evaluation:** normalized exact match, syntax/read-only validity, execution success, and result-based execution accuracy.

Spider source: https://yale-lily.github.io/spider
Spider code/format: https://github.com/taoyds/spider
Reproducible database archive used by the downloader: https://huggingface.co/datasets/HAL-9001/spider-databases
Base model: https://huggingface.co/google/flan-t5-small

## Architecture

```text
Spider questions + schemas + SQL
             │
             ▼
      preprocess / transpile
             │
             ▼
      FLAN-T5 + PyTorch
        fine-tuning
             │
             ▼
Natural-language question + selected MySQL schema
             │
             ▼
       generated SQL
             │
             ▼
     SQLGlot/read-only guard
             │
             ▼
          MySQL
             │
             ▼
      Pandas result table
             │
             ▼
    Streamlit + Plotly
```

## Repository structure

```text
QueryMind_Spider_MySQL/
├── app.py
├── requirements.txt
├── .env.example
├── src/
│   ├── model.py
│   ├── inference.py
│   ├── mysql_db.py
│   ├── schema.py
│   ├── prompting.py
│   ├── spider_data.py
│   ├── sql_utils.py
│   └── charts.py
├── scripts/
│   ├── download_spider.py
│   ├── prepare_training_data.py
│   ├── migrate_spider_to_mysql.py
│   ├── check_environment.py
│   └── smoke_test_offline.py
├── training/
│   └── train.py
├── evaluation/
│   ├── metrics.py
│   └── evaluate_mysql.py
├── tests/
├── notebooks/
├── docs/
└── sql/
```

# Setup on Windows

## 1. Install prerequisites

Install:

- Python 3.11 or 3.12 recommended
- MySQL Server 8.x
- MySQL Workbench (optional but convenient)
- VS Code
- Git (optional)

Make sure MySQL Server is running.

## 2. Create the Python environment

From the project folder:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Or run:

```bat
setup_windows.bat
```

The setup script also downloads Spider and prepares the training JSONL files.

## 3. Configure MySQL

Copy:

```text
.env.example  ->  .env
```

Edit `.env`:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=YOUR_MYSQL_PASSWORD
MYSQL_DATABASE_PREFIX=spider_
MODEL_PATH=models/querymind-flan-t5-small
BASE_MODEL=google/flan-t5-small
```

Do not commit `.env`.

## 4. Download the real Spider dataset

```bat
python scripts\download_spider.py
```

The downloader retrieves `spider_data.zip`, verifies its published SHA-256 checksum, and extracts:

```text
data/raw/spider/spider_data/
├── train_spider.json
├── dev.json
├── tables.json
└── database/
```

The archive contains the original Spider SQLite databases used for execution-based evaluation.

## 5. Prepare MySQL-target training data

```bat
python scripts\prepare_training_data.py
```

Outputs:

```text
data/processed/train.jsonl
data/processed/dev.jsonl
```

Each row contains:

```json
{
  "db_id": "...",
  "question": "...",
  "schema": "...",
  "input_text": "schema-aware FLAN-T5 prompt",
  "target_text": "MySQL SQL"
}
```

When SQLGlot is installed, Spider's SQLite-style SQL is transpiled to MySQL syntax for the target sequence.

## 6. Migrate Spider databases to MySQL

For a fast demo, migrate one database:

```bat
python scripts\migrate_spider_to_mysql.py --db-id concert_singer
```

Or the default demo set:

```bat
python scripts\migrate_spider_to_mysql.py
```

For every database referenced by the Spider dev split:

```bat
python scripts\migrate_spider_to_mysql.py --split dev
```

For all Spider databases:

```bat
python scripts\migrate_spider_to_mysql.py --all
```

A Spider database such as `concert_singer` becomes:

```text
spider_concert_singer
```

in MySQL.

The migration intentionally focuses on preserving data for analytics/query execution; it does not recreate every SQLite constraint or index.

# Model training

## Recommended first smoke training

Before a full run:

```bat
python training\train.py ^
  --epochs 1 ^
  --batch-size 4 ^
  --limit-train 64 ^
  --limit-dev 32 ^
  --output models\smoke-model
```

This confirms the full tokenization/training/save path.

## Full FLAN-T5-small training

A GPU runtime (Colab/Kaggle/local NVIDIA GPU) is recommended:

```bash
python training/train.py \
  --base-model google/flan-t5-small \
  --epochs 3 \
  --batch-size 8 \
  --lr 3e-4 \
  --output models/querymind-flan-t5-small
```

The script uses:

- `torch.utils.data.Dataset`
- `DataLoader`
- FLAN-T5 encoder-decoder forward pass
- token-level sequence loss
- `loss.backward()`
- `torch.optim.AdamW`
- gradient clipping
- LR scheduling
- mixed precision on CUDA
- best validation-loss checkpoint saving

No model accuracy number should be claimed until this training and evaluation are actually run.

# Run the application

After a trained model exists at `MODEL_PATH` and at least one Spider database is migrated to MySQL:

```bat
streamlit run app.py
```

Or:

```bat
run_app.bat
```

The app lets the user:

1. select a migrated Spider MySQL database;
2. inspect its live schema;
3. enter a natural-language question;
4. generate SQL with FLAN-T5;
5. validate the SQL as read-only;
6. execute it against MySQL;
7. view the table and an automatic Plotly chart when appropriate.

# Evaluation

For meaningful execution evaluation, migrate the dev databases first:

```bat
python scripts\migrate_spider_to_mysql.py --split dev
```

Then run:

```bat
python evaluation\evaluate_mysql.py --limit 100
```

For the complete dev split:

```bat
python evaluation\evaluate_mysql.py --limit 0
```

Outputs:

```text
results/evaluation.csv
results/evaluation.summary.json
```

Metrics reported by the local evaluator:

- SQL validity/read-only rate
- execution success rate
- result-based execution accuracy
- normalized exact match

The official Spider evaluator is more sophisticated; use it as an additional benchmark if you need leaderboard-comparable numbers.

# Safety design

Generated SQL is never executed blindly.

The system:

1. strips markdown code fences;
2. rejects multiple statements;
3. parses MySQL SQL with SQLGlot when available;
4. rejects INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/etc.;
5. requires a SELECT node;
6. executes only after validation;
7. limits fetched rows;
8. sets a MySQL execution-time limit.

For a production deployment, use a dedicated MySQL account with `SELECT` permission only. That database permission is the strongest safety boundary.

# Tests

Offline tests do not need MySQL, Spider download, or model weights:

```bat
python scripts\smoke_test_offline.py
pytest -q
```

They cover:

- Spider `tables.json` schema parsing;
- foreign-key relationship serialization;
- prompt construction;
- Spider-format training-row preprocessing;
- SQL safety checks;
- identifier/type migration helpers.

See `docs/VERIFICATION.md` for the exact build-time verification status.

# Honest limitations

- FLAN-T5-small is intentionally lightweight; complex Spider joins/nested SQL may remain difficult.
- Migrating SQLite data to MySQL does not make SQLite and MySQL dialects identical; SQLGlot handles many syntax differences, not every semantic difference.
- Some Spider schemas are large enough that a 512-token model input can truncate schema context. A stronger V2 should add schema retrieval/linking rather than always sending the entire schema.
- Result-based execution comparison in this repository is a transparent local metric, not a drop-in replacement for the official Spider evaluator.
- The model should not be described as accurate until real held-out evaluation is run.

# Strong V2 improvements

1. CodeT5 or a stronger code model comparison.
2. Schema-linking/retrieval for large databases.
3. Constrained SQL decoding.
4. MySQL read-only application user.
5. Official Spider exact/execution evaluator integration.
6. Error analysis by JOIN, aggregation, column selection, nesting and filtering failures.
7. Docker Compose for MySQL + app reproducibility.


