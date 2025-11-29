````markdown
# 🧑‍🌾 AgriWealth Livestock AI Agent

---

## 🚀 Project Description

The **AgriWealth Livestock AI Agent** is an intelligent assistant for smallholder farmers, designed to help them make **data-driven decisions** regarding their livestock. It combines a **LangGraph state machine** with a **Google Gemini-based LLM** to process natural language queries and provide actionable insights from a **species-specific, segregated SQLite database** (`agriwealth_livestock.db`).

The agent focuses primarily on **translating natural language queries into safe SQL**, executing them against the database, and synthesizing results into **farmer-friendly advice**. It also supports simulated external advisory modes for health and general livestock management.

### Key Features

- **Segregated Database Schema:** 12 tables (4 Core, 4 Health, 4 Production) split by species (Cow, Goat, Sheep, Chicken).  
- **Multi-Step Workflow:** Input routing → SQL planning → Safe execution → Result synthesis → Error recovery.  
- **SQL Safety Enforcement:** Only `SELECT` queries are allowed, protecting sensitive farm data.  
- **Actionable Advice:** Raw data is contextualized with life-stage info (derived from birth dates) to provide recommendations that farmers can act on immediately.  

---

## 📊 Agent Interconnection Diagram
<img width="1024" height="1024" alt="Image" src="https://github.com/user-attachments/assets/c1afe1c8-57e4-4ff7-8d35-808a499d0382" />
---

## 📁 Files & Modules Overview

| File / Module | Description & Key Components |
| --- | --- |
| **`main.py`** | CLI interface and workflow runner. Initializes the `AgentState` and invokes the compiled LangGraph workflow (`app`). Handles user inputs and displays results. |
| **`agriwealth_agent.py`** | Core agent logic and LangGraph workflow. Includes: <br>• `get_database_schema()` – Returns schema of all tables.<br>• `get_llm()` – LLM factory for Gemini integration.<br>• `is_sql_safe()` – SQL safety validator.<br>• Agent functions: `db_entry_agent`, `convert_nl_to_sql`, `execute_multi_sql`, `generate_human_readable_answer`, `regenerate_query`.<br>• Compilation of the **LangGraph workflow**. |
| **`state.py`** | Central data models. Defines `AgentState` (TypedDict) to maintain context, and Pydantic models (`ConvertToSQL`, `RewrittenQuestion`) for structured LLM output. |
| **`generate_data.py`** | Utility to generate and populate `agriwealth_livestock.db` with synthetic, realistic livestock data following the 12-table schema. |
| **`agriwealth_livestock.db`** | Runtime SQLite database containing livestock records (generated via `generate_data.py`). **Not committed to Git.** |
| **`.env`** | Environment variables (e.g., `GEMINI_API_KEY`). **Not committed to Git.** |

---

## ⚙️ Setup & Installation

### Prerequisites

1. **Python 3.9+**  
2. Required libraries:

```bash
pip install langgraph langchain-google-genai sqlalchemy pydantic python-dotenv faker
````

### Setup Steps

1. **API Key Configuration**

Create `.env` in the project root:

```
GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
```

2. **Generate Database**

```bash
python generate_data.py
```

This creates `agriwealth_livestock.db` with all 12 tables and synthetic data.

3. **Run the Main Application**

```bash
python main.py
```

This launches the interactive CLI for querying livestock data.

---

## 👩‍💻 Usage Instructions (Agent Modes)

The agent operates in **3 modes**, which determine the workflow path in LangGraph:

| Mode  | Entry Point               | Function                                                                     | Example Query                                                   |
| ----- | ------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **1** | `db_entry_agent`          | **Core data analysis:** Translates NL → SQL → Executes → Synthesizes results | *“What are the last 3 vaccination dates for cow COW.1?”*        |
| **2** | `disease_diagnosis_agent` | **Simulated urgent health advice** based on symptoms                         | *“My goat has fever and diarrhea, what is the best first aid?”* |
| **3** | `web_research_agent`      | **General advice / best practices** using simulated external info            | *“How often should I deworm my goats?”*                         |

---

## 💾 Database Schema

The database is fully **segregated** to prevent accidental cross-species queries.

### Table Naming Convention

```
[SPECIES]_[CATEGORY]
```

* SPECIES: `cow`, `goat`, `sheep`, `chicken`
* CATEGORY: `health_records`, `production_records`

### Core Tables (e.g., `cows`)

| Column       | Type      | Description                                 |
| ------------ | --------- | ------------------------------------------- |
| `animal_id`  | TEXT (PK) | Unique identifier (e.g., `COW.1`)           |
| `name`       | TEXT      | Animal name                                 |
| `breed`      | TEXT      | Breed                                       |
| `birth_date` | DATE      | Used for age calculation                    |
| `status`     | TEXT      | `Active`, `Sold`, `Deceased`, `Quarantined` |
| `weight_kg`  | REAL      | Current weight                              |

### Health Records Tables (e.g., `cow_health_records`)

| Column        | Type         | Description                                                  |
| ------------- | ------------ | ------------------------------------------------------------ |
| `record_id`   | INTEGER (PK) | Record primary key                                           |
| `animal_id`   | TEXT (FK)    | Links to core table                                          |
| `record_date` | DATE         | Date of the health event                                     |
| `record_type` | TEXT         | `Vaccination`, `Treatment`, `Deworming`, `Injury`, `Symptom` |
| `cost`        | REAL         | Event cost                                                   |

### Production Records Tables (e.g., `goat_production_records`)

| Column          | Type         | Description                          |
| --------------- | ------------ | ------------------------------------ |
| `production_id` | INTEGER (PK) | Record primary key                   |
| `animal_id`     | TEXT (FK)    | Links to core table                  |
| `record_date`   | DATE         | Date of measurement                  |
| `metric_type`   | TEXT         | Metric type (e.g., `Milk Yield (L)`) |
| `value`         | REAL         | Measurement value                    |

---

## 🤝 Contributing Guidelines

1. **SQL Safety:** All generated queries must pass `is_sql_safe` (only `SELECT` allowed).
2. **Species Segregation:** Respect the 12-table schema.
3. **State Consistency:** Agents must maintain correct `AgentState` across workflow.

---

## 🤖 Acknowledgement

*LangGraph orchestration, error handling, and schema definition were refined with the assistance of **Gemini 2.5 Pro** AI.*

---

## ⚖️ License

This project is open-source under the **MIT License**.


