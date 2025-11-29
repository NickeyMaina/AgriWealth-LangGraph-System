import sqlite3
import random
from datetime import datetime, timedelta
from faker import Faker
from typing import Dict, List, Tuple

# --- CONFIGURATION ---
DB_NAME = "agriwealth_livestock.db"
NUM_COWS = 40
NUM_GOATS = 50
NUM_CHICKENS = 150 
NUM_SHEEP = 20
NUM_ANIMALS = NUM_COWS + NUM_GOATS + NUM_CHICKENS + NUM_SHEEP 

# Current date MUST match the current date logic in the agent for age calculation to work
CURRENT_DATE = datetime(2025, 11, 26) 

# Record targets
NUM_HEALTH_RECORDS = NUM_ANIMALS * 3 
NUM_PRODUCTION_RECORDS = NUM_ANIMALS * 4 

fake = Faker('en_US')

# Helper function to get the correct table name based on animal type and record category
def get_table_name(animal_type: str, category: str) -> str:
    """Returns the species-specific table name."""
    prefix = animal_type.lower()
    if category == 'health':
        return f"{prefix}_health_records"
    elif category == 'production':
        return f"{prefix}_production_records"
    return prefix 

def generate_db_data():
    """Generates the SQLite database with synthetic livestock data based on the fully segregated schema and TEXT IDs."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 1. Drop Tables ---
    table_names_to_drop = [
        "cows", "goats", "sheeps", "chickens",
        "cow_health_records", "goat_health_records", "sheep_health_records", "chicken_health_records",
        "cow_production_records", "goat_production_records", "sheep_production_records", "chicken_production_records",
        "production_records", "health_records", "farm_transactions"
    ]
    for table in table_names_to_drop:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
    # --- 2. Create All 12 Species-Specific Tables ---
    try:
        species = ['cows', 'goats', 'sheeps', 'chickens']
        
        # --- NEW SPECIES-SPECIFIC CORE ANIMAL TABLES ---
        common_animal_columns = """
            animal_id TEXT PRIMARY KEY, 
            name TEXT NOT NULL,
            breed TEXT,
            tag_id TEXT UNIQUE,
            birth_date DATE,
            acquisition_date DATE,
            status TEXT NOT NULL CHECK(status IN ('Active', 'Sold', 'Deceased', 'Quarantined')),
            sex TEXT CHECK(sex IN ('Male', 'Female', 'Unknown')),
            weight_kg REAL,
            last_fed_time DATETIME
        """
        for s in species:
            cursor.execute(f"CREATE TABLE {s} ({common_animal_columns})")

        # --- NEW SPECIES-SPECIFIC HEALTH TABLES ---
        common_health_columns = """
            record_id INTEGER PRIMARY KEY,
            animal_id TEXT NOT NULL, 
            record_date DATE NOT NULL,
            record_type TEXT NOT NULL CHECK(record_type IN ('Vaccination', 'Treatment', 'Deworming', 'Injury', 'Symptom')),
            description TEXT,
            cost REAL,
            administered_by TEXT
        """
        for s in species:
            cursor.execute(f"CREATE TABLE {s[:-1]}_health_records ({common_health_columns})")

        # --- NEW SPECIES-SPECIFIC PRODUCTION TABLES ---
        # animal_id is now TEXT NOT NULL
        common_production_columns = """
            production_id INTEGER PRIMARY KEY,
            animal_id TEXT NOT NULL, 
            record_date DATE NOT NULL,
            metric_type TEXT NOT NULL, 
            value REAL NOT NULL,
            notes TEXT
        """
        for s in species:
            cursor.execute(f"CREATE TABLE {s[:-1]}_production_records ({common_production_columns})")
            
    except sqlite3.Error as e:
        print(f"Error setting up database: {e}")
        return

    # --- 3. Generate and Separate Animal Data ---
    cows_data: List[Tuple] = []
    goats_data: List[Tuple] = []
    chickens_data: List[Tuple] = []
    sheeps_data: List[Tuple] = []
    animal_records_map: Dict[str, str] = {} # Map ID (TEXT) -> Type (str)
    unique_tags = set()
    
    # Trackers for incremental ID generation (e.g., COW.1, COW.2, ...)
    type_counts = {'cow': 0, 'goat': 0, 'chicken': 0, 'sheep': 0}

    
    animal_types = (['cow'] * NUM_COWS + 
                    ['goat'] * NUM_GOATS + 
                    ['chicken'] * NUM_CHICKENS + 
                    ['sheep'] * NUM_SHEEP)
    random.shuffle(animal_types)

    integer_ids = list(range(1, NUM_ANIMALS + 1)) 
    
    quarantined_indices = random.sample(integer_ids, 5) 

    for i in integer_ids:
        type = animal_types[i - 1]
        type_prefix = type.upper()
        
        # --- NEW ID GENERATION ---
        type_counts[type] += 1
        animal_id = f"{type_prefix}.{type_counts[type]}"
        # -------------------------

        name = fake.first_name()
        sex = random.choice(['Male', 'Female'])
        
        # Tag ID (still numerical based, but unique)
        tag_id = None
        while tag_id is None or tag_id in unique_tags:
             tag_id = f"{type_prefix[0]}-{random.randint(1000, 9999)}"
        unique_tags.add(tag_id)
        
        # Birth Date Logic
        age_group = random.choices(['newborn', 'juvenile', 'mature', 'old'], weights=[5, 25, 60, 10], k=1)[0]
        if age_group == 'newborn':
            birth_date = (CURRENT_DATE - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d')
        elif age_group == 'juvenile':
            birth_date = (CURRENT_DATE - timedelta(days=random.randint(31, 730))).strftime('%Y-%m-%d')
        elif age_group == 'mature':
            birth_date = (CURRENT_DATE - timedelta(days=random.randint(731, 1825))).strftime('%Y-%m-%d')
        else:
            birth_date = (CURRENT_DATE - timedelta(days=random.randint(1826, 3650))).strftime('%Y-%m-%d')

      
        status = 'Active'
        if i > NUM_ANIMALS * 0.9: 
            status = random.choice(['Sold', 'Deceased'])
        if i in quarantined_indices:
            status = 'Quarantined'

        # Breed and Weight Logic
        breed = "Local"
        weight = random.uniform(5, 50)
        
        if type == 'cow':
            breed = random.choice(['Dairy Cross', 'Boran', 'Friesian'])
            weight = random.uniform(250, 600)
            target_list = cows_data
        elif type == 'goat':
            breed = random.choice(['Boer', 'Saanen', 'Local'])
            weight = random.uniform(30, 80)
            target_list = goats_data
        elif type == 'chicken':
            breed = random.choice(['Broiler', 'Layer', 'Kienyeji'])
            weight = random.uniform(1.5, 3.5)
            target_list = chickens_data
        elif type == 'sheep':
            breed = random.choice(['Dorper', 'Red Maasai', 'Merino'])
            weight = random.uniform(40, 90)
            target_list = sheeps_data

        acquisition_date = (datetime.strptime(birth_date, '%Y-%m-%d') + timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d')
        last_fed_time = (CURRENT_DATE - timedelta(hours=random.randint(1, 12), minutes=random.randint(0, 59))).strftime('%Y-%m-%d %H:%M:%S')

        # Record the animal's type for later health/production linking
        animal_records_map[animal_id] = type 
        
        # Data tuple for insertion
        animal_data = (animal_id, name, breed, tag_id, birth_date, acquisition_date, status, sex, round(weight, 2), last_fed_time)
        target_list.append(animal_data)

    # Insert into species-specific core tables
    common_fields = "animal_id, name, breed, tag_id, birth_date, acquisition_date, status, sex, weight_kg, last_fed_time"
    common_placeholders = "?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
    
    cursor.executemany(f"INSERT INTO cows ({common_fields}) VALUES ({common_placeholders})", cows_data)
    cursor.executemany(f"INSERT INTO goats ({common_fields}) VALUES ({common_placeholders})", goats_data)
    cursor.executemany(f"INSERT INTO sheeps ({common_fields}) VALUES ({common_placeholders})", sheeps_data)
    cursor.executemany(f"INSERT INTO chickens ({common_fields}) VALUES ({common_placeholders})", chickens_data)


    # --- 4. Health Records (Species-Specific Routing) ---
    health_records_map: Dict[str, List[Tuple]] = {s[:-1]: [] for s in species}
    record_types = ['Vaccination', 'Treatment', 'Deworming', 'Injury', 'Symptom']
    
    # We now iterate over the TEXT animal IDs
    all_animal_ids = list(animal_records_map.keys())
    
    for i in range(NUM_HEALTH_RECORDS):
        animal_id = random.choice(all_animal_ids)
        animal_type = animal_records_map[animal_id]
        
        if i < 10: 
             record_date = (CURRENT_DATE - timedelta(days=random.randint(0, 1))).strftime('%Y-%m-%d')
        else:
            record_date = (CURRENT_DATE - timedelta(days=random.randint(1, 730))).strftime('%Y-%m-%d')
        
        record_type = random.choices(record_types, weights=[55, 25, 10, 5, 5], k=1)[0]
        
        description = f"{record_type} event: {fake.text(max_nb_chars=50)}"
        if record_type == 'Vaccination':
             description = random.choice(['FMD vaccine administered', 'Blackquarter dose', 'Peste des Petits Ruminants (PPR) vaccine'])
        elif record_type == 'Treatment':
             description = random.choice(['Antibiotics for mastitis', 'Acaricide dip for ticks', 'Fluid therapy'])
        elif record_type == 'Symptom':
             description = random.choice(['Sudden drop in feed intake', 'Lethargy and fever', 'Diarrhea'])
        elif record_type == 'Injury':
             description = random.choice(['Deep laceration on leg', 'Broken horn', 'Eye infection'])

        cost = round(random.uniform(50, 5000), 2)
        administered_by = random.choice(['Vet', 'Farm Hand', 'Self'])
        
        # Route to the correct species-specific list
        health_records_map[animal_type].append((None, animal_id, record_date, record_type, description, cost, administered_by))

    # Insert into species-specific health tables
    health_fields = "record_id, animal_id, record_date, record_type, description, cost, administered_by"
    health_placeholders = "?, ?, ?, ?, ?, ?, ?"
    for species_type, data_list in health_records_map.items():
        table_name = get_table_name(species_type, 'health')
        cursor.executemany(f"INSERT INTO {table_name} ({health_fields}) VALUES ({health_placeholders})", data_list)


    # --- 5. Production Records (Species-Specific Routing) ---
    production_records_map: Dict[str, List[Tuple]] = {s[:-1]: [] for s in species}
    prod_metrics = ['Milk Yield (L)', 'Weight Gain (kg)', 'Egg Count', 'Wool Yield (kg)']
    
    for i in range(NUM_PRODUCTION_RECORDS):
        animal_id = random.choice(all_animal_ids)
        record_date = (CURRENT_DATE - timedelta(days=random.randint(1, 180))).strftime('%Y-%m-%d')
        animal_type = animal_records_map[animal_id]

        # Determine the most relevant metric based on animal type
        metric_type = ""
        if animal_type in ['cow', 'goat']:
            metric_type = 'Milk Yield (L)' if random.random() < 0.7 else 'Weight Gain (kg)'
        elif animal_type == 'chicken':
            metric_type = 'Egg Count' if random.random() < 0.8 else 'Weight Gain (kg)'
        elif animal_type == 'sheep':
            metric_type = 'Wool Yield (kg)' if random.random() < 0.6 else 'Weight Gain (kg)'

        value = 0.0
        if metric_type == 'Milk Yield (L)':
            value = random.uniform(5.0, 30.0)
        elif metric_type == 'Weight Gain (kg)':
            value = random.uniform(0.1, 5.0)
        elif metric_type == 'Egg Count':
            value = random.randint(1, 7)
        elif metric_type == 'Wool Yield (kg)':
            value = random.uniform(1.0, 8.0)
            
        if random.random() < 0.02:
            value = 0.0

        notes = fake.text(max_nb_chars=30)
        
        # Route to the correct species-specific list
        production_records_map[animal_type].append((None, animal_id, record_date, metric_type, round(value, 2), notes))

    # Insert into species-specific production tables
    production_fields = "production_id, animal_id, record_date, metric_type, value, notes"
    production_placeholders = "?, ?, ?, ?, ?, ?"
    for species_type, data_list in production_records_map.items():
        table_name = get_table_name(species_type, 'production')
        cursor.executemany(f"INSERT INTO {table_name} ({production_fields}) VALUES ({production_placeholders})", data_list)
    
    conn.commit()
    conn.close()
    
    total_records = NUM_HEALTH_RECORDS + NUM_PRODUCTION_RECORDS
    print(f"Database {DB_NAME} successfully populated with {NUM_ANIMALS} animals across 4 core tables, and {total_records} records across 8 segregated health/production tables (12 tables total) using TEXT IDs.")
