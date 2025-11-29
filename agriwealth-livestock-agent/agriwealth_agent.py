import logging
import os
import datetime
from typing import Any, Dict, List, Optional, Callable
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import time
import math
from state import AgentState, ConvertToSQL, RewrittenQuestion # Import state models
from dotenv import load_dotenv e


load_dotenv()

# -------------------------
# Basic logging
# -------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agriwealth_agent")

# =============================================================
# DATABASE CONFIGURATION
# =============================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agriwealth_livestock.db")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# =============================================================
# LLM FACTORY
# =============================================================
def get_llm(temp: float = 0) -> ChatGoogleGenerativeAI:

    api_key = os.getenv("GEMINI_API_KEY", "")
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temp, api_key=api_key)

# =============================================================
# DATABASE SCHEMA INSPECTION (UPDATED FOR DETERMINISTIC SAMPLES)
# =============================================================
_SCHEMA_CACHE: Optional[str] = None
_CACHE_TIMESTAMP = 0
SCHEMA_CACHE_DURATION = 300  # 5 minutes
SPECIES = ['cow', 'goat', 'sheep', 'chicken']

# --- DETERMINISTIC SAMPLE DATA FOR LLM CONTEXT ---
SAMPLE_DATA = {
    'cows': """
| animal_id | name | breed | birth_date | status | weight_kg |
| :--- | :--- | :--- | :--- | :--- | :--- |
| COW.1 | Daisy | Friesian | 2024-05-15 | Active | 550.5 |
| COW.2 | Belle | Boran | 2023-01-20 | Quarantined | 320.0 |
| COW.3 | Fiona | Dairy Cross | 2020-07-01 | Active | 610.9 |
""",
    'cow_health_records': """
| record_id | animal_id | record_date | record_type | description | cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 101 | COW.1 | 2025-10-01 | Vaccination | FMD Booster | 1500.00 |
| 102 | COW.2 | 2025-11-20 | Symptom | High fever and reduced appetite | 0.00 |
| 103 | COW.1 | 2025-05-15 | Deworming | Ivermectin | 500.00 |
""",
    'cow_production_records': """
| production_id | animal_id | record_date | metric_type | value | notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 501 | COW.1 | 2025-11-25 | Milk Yield (L) | 18.5 | AM/PM average |
| 502 | COW.3 | 2025-11-25 | Milk Yield (L) | 0.0 | Dry off |
| 503 | COW.2 | 2025-10-01 | Weight Gain (kg) | 35.0 | Last monthly weighing |
""",
    'goats': """
| animal_id | name | breed | birth_date | status | weight_kg |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GOAT.5 | Daisy | Boer | 2023-04-01 | Active | 45.0 |
| GOAT.10 | Billy | Saanen | 2025-01-10 | Active | 20.5 |
| GOAT.15 | Lulu | Local | 2023-10-05 | Sold | 55.0 |
""",
    'goat_health_records': """
| record_id | animal_id | record_date | record_type | description | cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 201 | GOAT.5 | 2025-03-01 | Deworming | Fencendazole | 150.00 |
| 202 | GOAT.10 | 2025-09-15 | Vaccination | PPR | 80.00 |
| 203 | GOAT.5 | 2025-11-20 | Symptom | Coughing, nasal discharge | 0.00 |
""",
    'goat_production_records': """
| production_id | animal_id | record_date | metric_type | value | notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 601 | GOAT.5 | 2025-11-01 | Milk Yield (L) | 3.5 | Weekly average |
| 602 | GOAT.10 | 2025-10-10 | Weight Gain (kg) | 5.2 | Monthly gain |
""",
    'sheeps': """
| animal_id | name | breed | birth_date | status | weight_kg |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SHEEP.1 | Shaun | Dorper | 2023-01-01 | Active | 60.5 |
| SHEEP.2 | Dolly | Merino | 2024-08-10 | Active | 40.0 |
""",
    'sheep_health_records': """
| record_id | animal_id | record_date | record_type | description | cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 301 | SHEEP.1 | 2025-07-01 | Deworming | Oral drench | 250.00 |
| 302 | SHEEP.2 | 2025-10-05 | Injury | Laceration on flank | 1500.00 |
""",
    'sheep_production_records': """
| production_id | animal_id | record_date | metric_type | value | notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 701 | SHEEP.1 | 2025-09-01 | Wool Yield (kg) | 4.5 | Annual shearing |
| 702 | SHEEP.2 | 2025-11-01 | Weight Gain (kg) | 3.0 | Monthly check |
""",
    'chickens': """
| animal_id | name | breed | birth_date | status | weight_kg |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CHICKEN.1 | Red | Layer | 2025-05-01 | Active | 2.1 |
| CHICKEN.2 | Broil | Broiler | 2025-11-10 | Active | 0.8 |
""",
    'chicken_health_records': """
| record_id | animal_id | record_date | record_type | description | cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 401 | CHICKEN.1 | 2025-08-01 | Vaccination | Newcastle | 10.00 |
| 402 | CHICKEN.2 | 2025-11-20 | Symptom | Ruffled feathers, lethargy | 0.00 |
""",
    'chicken_production_records': """
| production_id | animal_id | record_date | metric_type | value | notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 801 | CHICKEN.1 | 2025-11-25 | Egg Count | 6 | Daily eggs this week |
| 802 | CHICKEN.2 | 2025-11-25 | Weight Gain (kg) | 0.5 | Market target |
"""
}
# -----------------------------------------------

def get_database_schema() -> str:
    """Return a textual description of the segregated livestock database schema."""
    global _SCHEMA_CACHE, _CACHE_TIMESTAMP
    current_time = time.time()
    
    SCHEMA_CACHE_DURATION = 300
    if _SCHEMA_CACHE is not None and (current_time - _CACHE_TIMESTAMP) < SCHEMA_CACHE_DURATION:
        logger.debug("Using cached database schema.")
        return _SCHEMA_CACHE

    parts: List[str] = []
    date_context = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts.append(f"**CURRENT REAL-WORLD DATE AND TIME: {date_context}**\n")
    
    inspector = inspect(engine)
    
    expected_tables: Dict[str, str] = {}
    for s in SPECIES:
        core = f"{s}s"
        health = f"{s}_health_records"
        production = f"{s}_production_records"
        
        expected_tables[core] = f"Core inventory for {s.upper()}s. PK: animal_id TEXT. Contains birth_date, status, weight_kg."
        expected_tables[health] = f"Health records for {s.upper()}s. FK: animal_id TEXT. Contains record_type, cost."
        expected_tables[production] = f"Production records for {s.upper()}s. FK: animal_id TEXT. Contains metric_type (Milk, Egg, Wool, Weight)."
        
    table_names = set(inspector.get_table_names())
    
    # --- Architecture Context (CRITICAL for LLM) ---
    parts.append("\n" + "="*60 + "\n")
    parts.append("## DATABASE ARCHITECTURE: FULLY SEGREGATED BY SPECIES\n")
    parts.append("Queries MUST JOIN tables with matching species prefixes.\n")
    parts.append("ALL animal_id columns are **TEXT (e.g., COW.1, GOAT.20, SHEEP.1)**\n")
    parts.append("### JOINING RULE:\n- Use SPECIES.animal_id = SPECIES_health_records.animal_id\n" + "="*60 + "\n")
    
    for table_name, description in expected_tables.items():
        parts.append(f"## Table: **{table_name}**\n")
        parts.append(f"*{description}*\n\n")
        
        if table_name not in table_names:
            parts.append("*(Table not present in database)*\n\n")
            continue
            
        parts.append("### Columns:\n")
        try:
            columns = inspector.get_columns(table_name)
            for col in columns:
                col_name = col['name']
                col_type = str(col['type']).split('(')[0]
                if col_name in ['animal_id', 'birth_date', 'status', 'record_date', 'metric_type', 'value']:
                    parts.append(f"- **{col_name}**: {col_type} (CRITICAL)\n")
                else:
                    parts.append(f"- {col_name}: {col_type}\n")
        except Exception as e:
            logger.error(f"Could not inspect columns for {table_name}: {e}")
            parts.append("*(Could not retrieve column information)*\n")
        
        parts.append("\n### Sample Data (Deterministic):\n")
        if table_name in SAMPLE_DATA:
            parts.append(SAMPLE_DATA[table_name])
        else:
             parts.append("*(No hardcoded sample data available)*\n")
        
        parts.append("\n")

    schema_text = "".join(parts)
    
    _SCHEMA_CACHE = schema_text
    _CACHE_TIMESTAMP = current_time
    logger.info("Database schema cache refreshed for 12 segregated tables.")
    
    return schema_text

def get_database_schema_cached() -> str:
    """Entry point for agents to retrieve the schema."""
    return get_database_schema()

# =============================================================
# SQL SAFETY VALIDATOR
# =============================================================
FORBIDDEN_SQL_PATTERNS = [
    "drop ", "alter ", "truncate ", "--", "/*", "*/", 
    "delete from", "update ", "insert into", "create table", 
    "grant ", "revoke " 
]
ALLOWED_TABLES = set()
for s in SPECIES:
    ALLOWED_TABLES.add(f"{s}s")
    ALLOWED_TABLES.add(f"{s}_health_records")
    ALLOWED_TABLES.add(f"{s}_production_records")

def is_sql_safe(query: str) -> bool:
    """Enhanced safety checks. Only SELECT queries are permitted."""
    if not query or not query.strip():
        return False
        
    q = query.strip().lower()
    
    if not q.startswith("select"):
        logger.warning("SQL rejected: Must start with SELECT.")
        return False

    if ";" in q and q.count(";") > 1:
        logger.warning("SQL rejected: multiple semicolons.")
        return False
        
    for pat in FORBIDDEN_SQL_PATTERNS:
        if pat in q:
            logger.warning("SQL rejected due to forbidden pattern: %s", pat)
            return False
            
    if not any(table in q for table in ALLOWED_TABLES):
        logger.warning("SQL rejected: no allowed segregated livestock tables referenced.")
        return False
            
    return True

# =============================================================
# AGENT STATE & UTILS
# =============================================================
def _get_chat_prompt_and_llm(prompt_messages: List[Any], structured_model: Optional[Any] = None, temp: float = 0):
    """Helper to initialize prompt and LLM chain."""
    prompt = ChatPromptTemplate.from_messages(prompt_messages)
    llm = get_llm(temp)
    
    if structured_model is not None:
        structured = llm.with_structured_output(structured_model)
    else:
        structured = llm
        
    return prompt, structured

def detect_entity(question: str) -> str:
    """Heuristically detects the primary species entity in the question."""
    q = (question or "").lower()
    if any(word in q for word in ["cow", "bull", "calf"]):
        return "cow"
    if any(word in q for word in ["goat", "kid", "nanny"]):
        return "goat"
    if any(word in q for word in ["sheep", "lamb", "ewe"]):
        return "sheep"
    if any(word in q for word in ["chicken", "fowl", "poultry", "hen", "rooster"]):
        return "chicken"
    if any(word in q for word in ["animal", "livestock", "stock", "inventory"]):
        return "general"
    return "general"
    
def router_entry_func(state: AgentState) -> AgentState:
    """A simple pass-through function used as the initial node to ensure a dict is returned."""
    return state

# =============================================================
# AGENT FUNCTIONS (Logic uses new schema context)
# =============================================================

# --- DB ENTRY AGENT (Entry for Mode 1) ---
def db_entry_agent(state: AgentState) -> AgentState:
    """
    Prepares user input for database querying by detecting animal type and setting intent.
    """

    if 'question' not in state or not state['question']:
        state['awaiting_input'] = True
        return state

    state['db_entry'] = state['question']
    state['animal_type'] = detect_entity(state['question'])
    state['intent'] = 'query_db'
    state['relevance'] = 'relevant'

    logger.info(
        "DB Entry Agent: Mode 1 forced. Intent=query_db | Animal=%s | Question=%s",
        state['animal_type'], state['db_entry']
    )

    return state

# --- WEB RESEARCH AGENT ---
def web_research_agent(state: AgentState) -> AgentState:
    """
    Uses the Google Search tool (placeholder) to find general livestock advice.
    """
    state.setdefault("animal_type", "unknown")
    state.setdefault("question", "")
    
    TOOL_SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are AgriWealth AI, a livestock expert. Use the 'google_search' tool to find current, practical advice. Focus on: Prevention, symptoms, treatment, and best practices for {animal_type}. Provide: Clear, actionable advice suitable for smallholder farmers. """),
        ("human", "Farmer's question: {question}")
    ])
    
    llm_with_tool = get_llm(0.1)
    
    research_chain = TOOL_SYSTEM_PROMPT | llm_with_tool | StrOutputParser()

    logger.info("Invoking Web Research Agent (LIVE SEARCH PLACEHOLDER).")
    
    response = research_chain.invoke({
        "animal_type": state["animal_type"],
        "question": state["question"]
    })
    
    state["query_result"] = response
    logger.info("Web Research Agent produced livestock advice.")
    return state

# --- DISEASE DIAGNOSIS AGENT ---
def disease_diagnosis_agent(state: AgentState) -> AgentState:
    """
    Uses the Google Search tool (placeholder) for visual diagnosis and immediate actions.
    """
    state.setdefault("animal_type", "unknown")
    state.setdefault("question", "")
    
    # Mode 2 includes the specific image request for visual aid
    DIAGNOSIS_SYSTEM_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are AgriHealth AI, a visual livestock disease expert. Analyze the image and question about {animal_type}. Process: 1. Describe visible symptoms. 2. Use 'google_search' for matching diseases. 3. Provide likely diagnosis and immediate actions. 4. ALWAYS recommend consulting a local veterinarian. """),
        ("human", "Visual diagnosis request: {question}")
    ])
    
    llm_with_tool = get_llm(0.1)
    diagnosis_chain = DIAGNOSIS_SYSTEM_PROMPT | llm_with_tool | StrOutputParser()

    logger.info("Invoking Disease Diagnosis Agent (LIVE SEARCH PLACEHOLDER).")
    
    response = diagnosis_chain.invoke({
        "animal_type": state["animal_type"], 
        "question": state["question"]
    })
    
    state["query_result"] = response
    logger.info("Disease Diagnosis Agent completed analysis.")
    return state

# --- SQL GENERATOR AGENT (PLANNER) ---
def convert_nl_to_sql(state: AgentState) -> AgentState:
    """
    Converts the natural language question into 1-5 optimized SQL SELECT queries.
    """

    state.setdefault("db_entry", "")
    state.setdefault("animal_type", "unknown")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are an **Expert SQL Data Analyst and Query Planner**.

Your ONLY task is to convert the user's database question into **1 to 5 optimized SQL SELECT queries** required to fully answer the question.

=========================
🚨 CRITICAL SQL RULES 🚨
=========================

1. ✅ TIME-AWARE QUERIES
   - If age, duration, pregnancy, vaccination, or history is involved,
     you MUST use the CURRENT REAL-WORLD DATE from the schema.

2. ✅ STRICT SPECIES JOIN RULE
   - You may ONLY join tables with the SAME species prefix.
   - Example:
     ✅ cows JOIN cow_health_records
     ❌ cows JOIN goat_health_records

3. ✅ ANIMAL ID FORMAT
   - All animal IDs are TEXT strings.
   - Always wrap in single quotes:
     Example: 'COW.1', 'GOAT.5'

4. ✅ QUERY TYPE ENFORCEMENT
   - You MUST ONLY output SELECT statements.
   - ❌ NEVER generate:
     INSERT, UPDATE, DELETE, DROP, CREATE, ALTER

5. ✅ MULTI-QUERY DECOMPOSITION
   - If multiple datasets are required:
     → Split them into multiple focused queries.
   - Maximum queries allowed: 5
   
6. ✅ SORTING:
   - Do NOT use ORDER BY in the query. All sorting must be done by the synthesis agent.

=========================
📦 DATABASE SCHEMA & CURRENT DATE
=========================
{schema}

=========================
🐾 QUESTION ABOUT {animal_type}
=========================
"""),
        ("human", "{db_entry}")
    ])

    llm = get_llm(0)
    structured = llm.with_structured_output(ConvertToSQL)
    chain = prompt | structured

    logger.info("Invoking Multi-Query SQL Planner Agent using db_entry.")

    result = chain.invoke({
        "schema": get_database_schema_cached(),
        "animal_type": state["animal_type"],
        "db_entry": state["db_entry"]
    })

    state["sql_query"] = result.sql_queries

    logger.info("Generated %d SQL queries.", len(state["sql_query"]))

    return state

# --- SQL EXECUTION LAYER ---
def execute_multi_sql(state: AgentState) -> AgentState:
    """
    Safely executes the list of SQL SELECT queries generated by the SQL Planning Agent.
    """

    queries = state.get("sql_query", [])
    session = SessionLocal()
    combined_results = {}
    error_count = 0

    for i, query in enumerate(queries):
        query = query.strip()
        logger.debug(f"Attempting to execute SQL {i+1}: {query}")

        # Mandatory SQL safety check
        if not is_sql_safe(query):
            combined_results[f"Query_{i+1}_Refused"] = "Refused to execute unsafe SQL."
            error_count += 1
            logger.warning(f"SQL {i+1} blocked by safety policy.")
            continue

        try:
            # Enforce max row limit for safety
            query_to_execute = query
            if 'limit' not in query.lower():
                query_to_execute = f"{query} LIMIT 100"

            result = session.execute(text(query_to_execute))
            rows = result.fetchall()
            keys = result.keys()

            combined_results[f"Query_{i+1}_Success"] = [
                dict(zip(keys, row)) for row in rows
            ]

            logger.info(
                f"SQL {i+1} executed successfully. Rows returned: {len(rows)}"
            )

        except Exception as e:
            session.rollback()
            combined_results[f"Query_{i+1}_Error"] = f"Error executing: {str(e)}"
            error_count += 1
            logger.exception(f"SQL {i+1} execution error.")

    session.close()

    state["query_rows"] = combined_results
    state["query_result"] = str(combined_results)
    state["sql_error"] = (error_count > 0)

    return state


# --- RESPONSE FORMATTING AGENT (SYNTHESIS) ---
def generate_human_readable_answer(state: AgentState) -> AgentState:
    """
    Converts raw SQL query results into a clear, simple, and highly actionable answer.
    (Used ONLY for Mode 1: Database Query)
    """

    state.setdefault("sql_query", [])
    state.setdefault("query_result", "")
    state.setdefault("query_rows", {})
    state.setdefault("sql_error", False)
    state.setdefault("animal_type", "unknown")
    state.setdefault("db_entry", "")

    # =========================
    # 🚨 CASE 1: SQL ERROR
    # =========================
    if state["sql_error"]:
        prompt_text = f"""
Animal Type: {state['animal_type']}

SQL Error Details:
{state['query_result']}

TASK:
Create a polite, friendly message for the farmer explaining:
- That part of the data could not be retrieved
- That the system is safe
- That they should rephrase or simplify their question
- Keep the tone calm, helpful, and respectful
"""

    # =========================
    # 🚨 CASE 2: NO DATA FOUND
    # =========================
    elif not any(state["query_rows"].values()):
        prompt_text = f"""
Animal Type: {state['animal_type']}
Original Question: {state['db_entry']}

No records were found in the system.

TASK:
Politely advise the farmer on what may be missing, such as:
- Birth records
- Health records
- Vaccination history
- Weight or feeding data

Encourage proper record keeping in a supportive way.
"""

    # =========================
    # ✅ CASE 3: DATA AVAILABLE → FULL SYNTHESIS
    # =========================
    else:
        current_date_info = next(
            (line for line in get_database_schema_cached().split('\n')
             if 'CURRENT REAL-WORLD DATE' in line),
            'No current date provided.'
        )
        
        prompt_text = f"""
Animal Type: {state['animal_type']}
Original Question: {state['db_entry']}

CONTEXT:
- {current_date_info}
- Raw Multi-Query Results:
{state['query_result']}

=========================
🚨 MANDATORY SYNTHESIS RULES 🚨
=========================

1. ✅ AGE CALCULATION
   - If a birth date exists:
     → Mentally calculate the animal’s REAL AGE using the CURRENT DATE.

2. ✅ LIFE STAGE DETERMINATION
   - Based on the calculated age, clearly identify one:
     - Newborn
     - Weanling
     - Growing
     - Breeding age
     - Mature
     - Old

3. ✅ LIFE-STAGE SAFE ADVICE
   - You MUST give advice that fits ONLY the true life stage.

4. ✅ FULL DATA SYNTHESIS
   - Combine:
     - Health data
     - Vaccination records
     - Feeding
     - Weight
     - Production
   - Present them as ONE clear conclusion.

5. ✅ FARMER-FRIENDLY OUTPUT
   - Use:
     - Simple English
     - Clear bullet points
     - Short explanations
   - No scientific jargon.

6. ✅ MARKDOWN FORMATTING (REQUIRED)
   - Use:
     ## Headings
     - Bullet lists
     - Small summary tables (if useful)
     
=========================
🎯 FINAL GOAL
=========================
Produce a single, clear, practical answer that a farmer in Africa can confidently act on today.
"""

    # =========================
    # 🧠 LLM INVOCATION
    # =========================
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are the AgriWealth Livestock Synthesis AI. "
         "You transform database results into accurate, life-stage-safe, farmer-friendly advice. "
         "Strict age and life-stage enforcement is mandatory. "
         "Format using Markdown."),
        ("human", "{input}")
    ])

    chain = prompt | get_llm(0.3) | StrOutputParser()

    logger.info("Invoking livestock response synthesis LLM.")

    answer = chain.invoke({"input": prompt_text})

    state["query_result"] = answer

    logger.info("Generated farmer-friendly livestock answer.")

    return state


# --- QUERY RECOVERY AGENT ---
def regenerate_query(state: AgentState) -> AgentState:
    """
    Rewrites the farmer’s original question when SQL planning or execution fails.
    """

    state.setdefault("db_entry", "")
    state.setdefault("attempts", 0)
    state.setdefault("animal_type", "unknown")
    state.setdefault("query_result", "Unknown error")

    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system", """
You are a QUERY REWRITING AI for a livestock database system.

The previous SQL attempt FAILED with this error:
{sql_error}

Your task:
- Rewrite the farmer’s question so that it is:
  ✅ More precise
  ✅ Better structured
  ✅ Easier for SQL planning
- You MUST preserve:
  ✅ The original intent
  ✅ The animal species
  ✅ All numbers, dates, and IDs

ABSOLUTE PROHIBITIONS:
❌ Do NOT answer the question
❌ Do NOT change the meaning
❌ Do NOT introduce new requirements
❌ Do NOT generate SQL

Return ONLY the rewritten question.
"""),

        ("human", "Original question about {animal_type}: {question}")
    ])

    llm = get_llm(0)
    structured = llm.with_structured_output(RewrittenQuestion)
    chain = rewrite_prompt | structured

    logger.info("Invoking query rewriter LLM.")

    result = chain.invoke({
        "animal_type": state["animal_type"],
        "question": state["db_entry"],
        "sql_error": state["query_result"]
    })

    state["db_entry"] = result.question
    state["attempts"] = state.get("attempts", 0) + 1

    logger.info(
        "Regenerated DB question (attempt %d): %s",
        state["attempts"],
        state["db_entry"]
    )

    return state

# =============================================================
# ROUTERS
# =============================================================
def sql_error_router(state: AgentState) -> str:
    """Routes based on SQL execution success/failure."""
    sql_error = state.get("sql_error", False)
    if not sql_error:
        logger.info("SQL Error Router: No SQL errors detected. Proceeding to human-readable answer.")
        return "generate_human_readable_answer"
    else:
        logger.warning("SQL Error Router: SQL error detected. Routing to query regeneration.")
        return "regenerate_query"


def attempt_router(state: AgentState) -> str:
    """Prevents infinite retry loops by limiting attempts."""
    attempts = state.get("attempts", 0)
    if attempts < 3:
        logger.info("Attempt Router: Attempt %d allowed. Retrying SQL planning.", attempts)
        return "convert_to_sql"
    else:
        logger.error("Attempt Router: Maximum retry attempts reached. Terminating pipeline.")
        return "end_max_iterations"


def initial_path_router(state: AgentState) -> str:
    """Routes the user into the correct AI pipeline based on explicit menu selection."""
    mode = str(state.get("mode", "")).strip()
    logger.info("Initial Path Router received mode: %s", mode)

    if mode == '1':
        return "db_entry_agent"
    if mode == '2':
        return "disease_diagnosis_agent"
    if mode == '3':
        return "web_research_agent"

    state["router_error"] = f"Invalid mode selection: {mode}"
    return "invalid_mode_handler"

def invalid_mode_handler(state: AgentState) -> AgentState:
    """Handles invalid menu selections safely."""
    state["query_result"] = (
        "Invalid option selected.\n"
        "Please choose:\n"
        "1 → Animal Records\n"
        "2 → Disease Diagnosis\n"
        "3 → Web Research"
    )
    logger.warning("Invalid mode handled safely.")
    return state

# =============================================================
# WORKFLOW DEFINITION
# =============================================================
workflow = StateGraph(AgentState)

# --- Define NODES ---
workflow.add_node("router_entry_node", router_entry_func)
workflow.add_node("db_entry_agent", db_entry_agent) 
workflow.add_node("web_research_agent", web_research_agent)
workflow.add_node("disease_diagnosis_agent", disease_diagnosis_agent)

workflow.add_node("convert_to_sql", convert_nl_to_sql)
workflow.add_node("execute_sql", execute_multi_sql) 

workflow.add_node("generate_human_readable_answer", generate_human_readable_answer)
workflow.add_node("regenerate_query", regenerate_query)

workflow.add_node("invalid_mode_handler", invalid_mode_handler)

workflow.add_node(
    "end_max_iterations",
    lambda s: {
        **s,
        "query_result": (
            "I'm sorry, I reached the maximum number of attempts (3) to understand "
            "and query your records. Please try rephrasing your original question very simply."
        )
    }
)

# --- Set Default Entry Point ---
workflow.set_entry_point("router_entry_node")

# --- Define Edges ---
# Path 0: Initial Router (Routes 1, 2, 3)
workflow.add_conditional_edges(
    "router_entry_node",
    initial_path_router,
    {
        "db_entry_agent": "db_entry_agent",
        "disease_diagnosis_agent": "disease_diagnosis_agent",
        "web_research_agent": "web_research_agent",
        "invalid_mode_handler": "invalid_mode_handler"
    }
)

# Path 1: Database Chain
workflow.add_edge("db_entry_agent", "convert_to_sql")
workflow.add_edge("convert_to_sql", "execute_sql")
workflow.add_conditional_edges("execute_sql", sql_error_router, {
    "generate_human_readable_answer": "generate_human_readable_answer",
    "regenerate_query": "regenerate_query"
})
workflow.add_conditional_edges("regenerate_query", attempt_router, {
    "convert_to_sql": "convert_to_sql",
    "end_max_iterations": "end_max_iterations"
})

# Path 2 & 3: Direct Endings
workflow.add_edge("web_research_agent", END)
workflow.add_edge("disease_diagnosis_agent", END)
workflow.add_edge("generate_human_readable_answer", END)
workflow.add_edge("invalid_mode_handler", END)
workflow.add_edge("end_max_iterations", END)

app = workflow.compile()
logger.info("AgriWealth LangGraph Agent compiled successfully with explicit menu routing.")
