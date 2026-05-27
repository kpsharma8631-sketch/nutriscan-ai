#database.py

# =========================================================================
# 📊 NUTRISCAN AI MASTER NUTRITIONAL & DISEASE RISK DATASET
# =========================================================================
# Keys match exactly with folder structural names in the dataset directory.

FOOD_DATASET = {
    "burger": {
        "calories": 295,
        "risk_level": "High Risk",
        "risk_msg": "High in trans fats, sodium, and refined carbs.",
        "macros": {"Carbs": 45, "Protein": 15, "Fats": 40},
        "diseases": [
            {"name": "Obesity", "risk": "High long-term risk due to caloric density"},
            {"name": "Hypertension", "risk": "Elevated risk due to processed sodium levels"}
        ],
        "tests": [
            {"name": "Lipid Profile", "desc": "Monitors blood cholesterol and triglycerides"},
            {"name": "Blood Pressure", "desc": "Tracks arterial force fluctuations daily"}
        ]
    },
    "butter_naan": {
        "calories": 310,
        "risk_level": "Medium Risk",
        "risk_msg": "Rich in gluten and saturated fats from butter.",
        "macros": {"Carbs": 60, "Protein": 10, "Fats": 30},
        "diseases": [
            {"name": "Hyperlipidemia", "risk": "Saturated fats may elevate LDL levels"},
            {"name": "Celiac Sensitivity", "risk": "High refined white flour/gluten concentration"}
        ],
        "tests": [
            {"name": "Serum Cholesterol Test", "desc": "Measures good and bad fats in the bloodstream"}
        ]
    },
    "chai": {
        "calories": 45,
        "risk_level": "Low Risk",
        "risk_msg": "Safe in moderation; watch out for added processed sugars.",
        "macros": {"Carbs": 55, "Protein": 20, "Fats": 25},
        "diseases": [
            {"name": "Acidity / GERD", "risk": "Excessive consumption can trigger acid reflux"},
            {"name": "Hyperglycemia", "risk": "Risk increases if consumed with excessive white sugar"}
        ],
        "tests": [
            {"name": "HbA1c Test", "desc": "Evaluates 3-month average glucose saturation"}
        ]
    },
    "chapati": {
        "calories": 70,
        "risk_level": "Low Risk",
        "risk_msg": "Excellent source of complex carbohydrates and dietary fiber.",
        "macros": {"Carbs": 75, "Protein": 15, "Fats": 10},
        "diseases": [
            {"name": "None", "risk": "Highly recommended for standard daily dietary cycles"}
        ],
        "tests": [
            {"name": "Fasting Blood Sugar", "desc": "Standard checks for healthy insulin responses"}
        ]
    },
    "chole_bhature": {
        "calories": 450,
        "risk_level": "High Risk",
        "risk_msg": "Deep-fried bread combined with heavy lipid density spicy chickpea gravy.",
        "macros": {"Carbs": 50, "Protein": 12, "Fats": 38},
        "diseases": [
            {"name": "Fatty Liver (NAFLD)", "risk": "High intake of commercial oils blocks liver metabolism"},
            {"name": "Coronary Artery Disease", "risk": "Plaque formation risk due to trans-fat saturation"}
        ],
        "tests": [
            {"name": "Liver Function Test (LFT)", "desc": "Checks SGOT and SGPT enzyme balances"}
        ]
    },
    "dal_makhani": {
        "calories": 330,
        "risk_level": "Medium Risk",
        "risk_msg": "Rich source of proteins, but contains heavy dairy cream and butter.",
        "macros": {"Carbs": 40, "Protein": 18, "Fats": 42},
        "diseases": [
            {"name": "Hyperuricemia (Gout)", "risk": "High purine content in black lentils may increase uric acid"}
        ],
        "tests": [
            {"name": "Serum Uric Acid Test", "desc": "Measures uric acid accumulation in joints"}
        ]
    },
    "dhokla": {
        "calories": 160,
        "risk_level": "Low Risk",
        "risk_msg": "Steamed fermented food, very healthy and light on stomach.",
        "macros": {"Carbs": 70, "Protein": 18, "Fats": 12},
        "diseases": [
            {"name": "None", "risk": "Safe for weight management and diabetic control"}
        ],
        "tests": [
            {"name": "Post-Prandial Blood Sugar", "desc": "Checks glycemic load 2 hours after meals"}
        ]
    },
    "fried_rice": {
        "calories": 163,
        "risk_level": "Medium Risk",
        "risk_msg": "Contains high sodium sauces and high glycemic index polished rice.",
        "macros": {"Carbs": 65, "Protein": 10, "Fats": 25},
        "diseases": [
            {"name": "Water Retention", "risk": "High sodium values cause mild cellular swelling"}
        ],
        "tests": [
            {"name": "Kidney Function Test (KFT)", "desc": "Monitors blood urea nitrogen and serum creatinine"}
        ]
    },
    "idli": {
        "calories": 39,
        "risk_level": "Low Risk",
        "risk_msg": "Steamed, fermented, zero fat. Super safe breakfast choice.",
        "macros": {"Carbs": 80, "Protein": 15, "Fats": 5},
        "diseases": [
            {"name": "None", "risk": "Safe for heart patients and standard weight loss programs"}
        ],
        "tests": [
            {"name": "Basic Routine Health Check", "desc": "General monitoring metrics"}
        ]
    },
    "jalebi": {
        "calories": 150,
        "risk_level": "High Risk",
        "risk_msg": "Extremely high in sugar saturation and deep-fried in fats.",
        "macros": {"Carbs": 85, "Protein": 2, "Fats": 13},
        "diseases": [
            {"name": "Type-2 Diabetes", "risk": "Causes sudden spikes in systemic insulin demands"},
            {"name": "Dental Caries", "risk": "High sugar promotes bacterial enamel erosion"}
        ],
        "tests": [
            {"name": "Random Blood Sugar", "desc": "Instant verification of immediate systemic glucose shocks"}
        ]
    },
    "kaathi_rolls": {
        "calories": 320,
        "risk_level": "Medium Risk",
        "risk_msg": "Contains refined flour wraps and added oily sauces.",
        "macros": {"Carbs": 55, "Protein": 15, "Fats": 30},
        "diseases": [
            {"name": "Indigestion / Constipation", "risk": "Low dietary fiber blocks clean gut flow"}
        ],
        "tests": [
            {"name": "Stool Routine Examination", "desc": "Assesses gastrointestinal track health tracking"}
        ]
    },
    "kadai_paneer": {
        "calories": 350,
        "risk_level": "Medium Risk",
        "risk_msg": "Good cottage cheese protein density, but curry contains high oil.",
        "macros": {"Carbs": 20, "Protein": 25, "Fats": 55},
        "diseases": [
            {"name": "Atherosclerosis", "risk": "Excessive dense heavy dairy oils clog internal veins"}
        ],
        "tests": [
            {"name": "CT Coronary Calcium Scoring", "desc": "Scans plaque buildup inside heart lines"}
        ]
    },
    "kulfi": {
        "calories": 210,
        "risk_level": "High Risk",
        "risk_msg": "Concentrated milk solids loaded with high white sugar variants.",
        "macros": {"Carbs": 60, "Protein": 8, "Fats": 32},
        "diseases": [
            {"name": "Metabolic Syndrome", "risk": "Fats and sugar combination triggers insulin crashes"}
        ],
        "tests": [
            {"name": "Fasting Insulin Test", "desc": "Evaluates early pancreatic stress states"}
        ]
    },
    "masala_dosa": {
        "calories": 290,
        "risk_level": "Medium Risk",
        "risk_msg": "Fermented batter is healthy, but potato filling has high starch and oil.",
        "macros": {"Carbs": 65, "Protein": 10, "Fats": 25},
        "diseases": [
            {"name": "Blood Glucose Fluctuations", "risk": "Mashed potato core elevates sugar index quickly"}
        ],
        "tests": [
            {"name": "Oral Glucose Tolerance Test", "desc": "Measures body's ability to handle starch inputs"}
        ]
    },
    "momos": {
        "calories": 120,
        "risk_level": "Medium Risk",
        "risk_msg": "Steamed format is clean, but wrap contains raw processed refined maida.",
        "macros": {"Carbs": 70, "Protein": 15, "Fats": 15},
        "diseases": [
            {"name": "Bowel Irritation", "risk": "Refined flour tends to stick to intestinal inner liners"}
        ],
        "tests": [
            {"name": "Gut Health Colon Assessment", "desc": "Evaluates bacterial metabolic health profiles"}
        ]
    },
    "paani_puri": {
        "calories": 180,
        "risk_level": "Medium Risk",
        "risk_msg": "Low calories, but contains very high sodium tangy spice liquid water.",
        "macros": {"Carbs": 75, "Protein": 8, "Fats": 17},
        "diseases": [
            {"name": "Gastroenteritis", "risk": "High threat of waterborne micro-contamination if unhygienic"},
            {"name": "Acute Hypertension", "risk": "Excessive salt liquid elevates blood pressure temporary"}
        ],
        "tests": [
            {"name": "Widal / Typhoid Test", "desc": "Screening for bacterial intestinal track infections"}
        ]
    },
    "pakode": {
        "calories": 315,
        "risk_level": "High Risk",
        "risk_msg": "Deep fried gram flour snacks, accumulates high thermal lipid chains.",
        "macros": {"Carbs": 40, "Protein": 12, "Fats": 48},
        "diseases": [
            {"name": "Acrolein Toxicity", "risk": "Reheated oil generation increases cell inflammation"}
        ],
        "tests": [
            {"name": "High-Sensitivity CRP (hs-CRP)", "desc": "Measures total system internal cellular inflammation status"}
        ]
    },
    "pav_bhaji": {
        "calories": 400,
        "risk_level": "High Risk",
        "risk_msg": "Mashed mixed vegetables loaded with massive amounts of table butter.",
        "macros": {"Carbs": 50, "Protein": 8, "Fats": 42},
        "diseases": [
            {"name": "Visceral Fat Accumulation", "risk": "Heavy butter routing converts directly to abdominal fat"}
        ],
        "tests": [
            {"name": "Abdominal Ultrasound scan", "desc": "Measures fat layers around internal vital organs"}
        ]
    },
    "pizza": {
        "calories": 266,
        "risk_level": "High Risk",
        "risk_msg": "Processed cheese layers combined with white flour and sodium preservatives.",
        "macros": {"Carbs": 45, "Protein": 15, "Fats": 40},
        "diseases": [
            {"name": "Cardiovascular Blockages", "risk": "Saturated cheese lipids narrow blood passage routes"}
        ],
        "tests": [
            {"name": "Lipid Profile Matrix", "desc": "Tracks HDL, LDL, and VLDL distribution curves"}
        ]
    },
    "samosa": {
        "calories": 262,
        "risk_level": "High Risk",
        "risk_msg": "Deep-fried crispy white flour pocket filled with spiced starch potatoes.",
        "macros": {"Carbs": 52, "Protein": 8, "Fats": 40},
        "diseases": [
            {"name": "Arterial Plaque Build-up", "risk": "Frying maida creates high vascular degradation"},
            {"name": "Obesity Trigger", "risk": "High carbohydrate-fat density blocks normal metabolism"}
        ],
        "tests": [
            {"name": "Total Cholesterol Profile", "desc": "Assesses systemic cardiovascular structural ratios"}
        ]
    }
}
