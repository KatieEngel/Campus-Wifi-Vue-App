from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import geopandas as gpd
import pandas as pd
import json
import jellyfish
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
# Adjust these paths to where your actual data files are
DATA_DIR = BASE_DIR.parent / "data" 
PARQUET_FILE = DATA_DIR / "ten_min_occupancy_summary.parquet"
GEOJSON_FILE = DATA_DIR / "campus_buildings_categories.geojson"

# Global storage for data
db = {
    "data": None,     # The massive time-series data
    "campus": None,   # The building shapes
    "dates": []       # List of available dates
}

def classify_building_type(bldg_type):
    """Helper to categorize buildings"""
    if pd.isna(bldg_type): return 'Unknown'
    bldg_type_lower = str(bldg_type).lower()
    if any(keyword in bldg_type_lower for keyword in ['residence', 'dormitory', 'housing', 'greek']):
        return 'Residential'
    else:
        return 'Non-Residential'

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Loading Data...")
    
    # 1. Load Parquet Data
    try:
        if PARQUET_FILE.exists():
            df = pd.read_parquet(PARQUET_FILE)
            # ... (Existing cleaning logic) ...
            df['BLDG_CODE'] = df['BLDG_CODE'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['time_bin'] = pd.to_datetime(df['time_bin'])
            df['date_str'] = df['time_bin'].dt.strftime('%Y-%m-%d')
            df['hour'] = df['time_bin'].dt.hour
            df['minute'] = df['time_bin'].dt.minute
            df = df[df['date_str'] != "2025-04-13"]
            
            db["data"] = df
            db["dates"] = sorted(df['date_str'].unique().tolist())
            print(f"   ✅ Loaded {len(df)} occupancy records.")
        else:
            print(f"   ❌ Error: Parquet file not found at {PARQUET_FILE}")
            db["data"] = None
    except Exception as e:
        print(f"   ❌ CRITICAL PARQUET ERROR: {e}")
        db["data"] = None

    # 2. Load GeoJSON Geometry
    try:
        if GEOJSON_FILE.exists():
            with open(GEOJSON_FILE, 'r') as f:
                raw_geo = json.load(f)
            
            # SAFETY CHECK: Ensure we actually have features
            if not raw_geo.get('features'):
                print("   ❌ Error: GeoJSON file is empty or has no features.")
                db["campus"] = None
            else:
                campus_gdf = gpd.GeoDataFrame.from_features(raw_geo['features'], crs="EPSG:4326")
                
                if 'BLDG_CODE' in campus_gdf.columns:
                     campus_gdf['BLDG_CODE'] = campus_gdf['BLDG_CODE'].astype(str).str.replace(r'\.0$', '', regex=True)
                
                if 'BLDG_TYPE' in campus_gdf.columns:
                    campus_gdf['building_category'] = campus_gdf['BLDG_TYPE'].apply(classify_building_type)
                else:
                    campus_gdf['building_category'] = "Unknown"
                    
                db["campus"] = campus_gdf
                print(f"   ✅ Loaded {len(campus_gdf)} building geometries.")
        else:
            print(f"   ❌ Error: GeoJSON file not found at {GEOJSON_FILE}")
            db["campus"] = None
            
    except Exception as e:
        print(f"   ❌ CRITICAL GEOJSON ERROR: {e}")
        db["campus"] = None
        
    yield
    db["data"] = None
    db["campus"] = None

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow Vue to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTS ---

@app.get("/metadata")
def get_metadata():
    """Returns available dates and building categories"""
    if db["campus"] is None: return {"error": "Data not loaded"}
    
    return {
        "dates": db["dates"],
        "categories": list(db["campus"]['building_category'].unique())
    }

@app.get("/heatmap")
def get_heatmap(date: str, hour: int, minute: int):
    """
    Returns GeoJSON with occupancy data for a specific time slot.
    """
    df = db["data"]
    campus = db["campus"]
    
    if df is None or campus is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    # 1. Filter Data
    filtered = df[
        (df['date_str'] == date) & 
        (df['hour'] == hour) & 
        (df['minute'] == minute)
    ]
    
    # 2. Merge with Geometry
    # We do a LEFT join on the Campus map, so buildings with 0 occupancy still show up
    merged = campus.merge(
        filtered[['BLDG_CODE', 'occupancy']], 
        on='BLDG_CODE', 
        how='left'
    )
    
    # Fill NaN with 0
    merged['occupancy'] = merged['occupancy'].fillna(0).astype(int)
    
    # Convert to JSON string then dict
    return json.loads(merged.to_json())

@app.get("/timeline")
def get_timeline(date: str):
    """
    Returns aggregated timeline data for the charts
    """
    df = db["data"]
    if df is None: raise HTTPException(status_code=500, detail="Data not loaded")

    daily_data = df[df['date_str'] == date].copy()
    
    if daily_data.empty: return []

    # Aggregation Logic (Same as Streamlit)
    # 1. By Category
    df_cat = daily_data.groupby(['time_bin', 'building_category'])['occupancy'].sum().reset_index()
    
    # 2. Total
    df_total = daily_data.groupby('time_bin')['occupancy'].sum().reset_index()
    df_total['building_category'] = 'Total'
    
    combined = pd.concat([df_cat, df_total])
    
    # Format for frontend: List of dicts
    result = []
    for _, row in combined.iterrows():
        result.append({
            "time": row['time_bin'].strftime('%H:%M'),
            "category": row['building_category'],
            "occupancy": int(row['occupancy'])
        })
        
    return result

# configuring column names
NAME_COL = "BLDG_NAME" 
CODE_COL = "BLDG_CODE"

# --- NEW: Custom Colloquialisms Dictionary ---
# Keys must be lowercase for case-insensitive matching
CUSTOM_ALIASES = {
    "culc": "Clough Building",
    "clough": "Clough Building",
    "crc": "Campus Recreation Center",
    "mrdc": "Manufacturing Related Disciplines Complex",
    "coc": "College of Computing",
    "klaus": "Klaus Advanced Computing Building",
    "scheller": "Management Building",
    "student center": "John Lewis Student Center",
    "library": "Gilbert Memorial Library",
    "price": "Gilbert Memorial Library",
    "pg": "Gilbert Memorial Library"
}


def find_building_match(query: str, df: gpd.GeoDataFrame):
    """
    Returns a tuple: (MatchType, ResultData)
    MatchType: "exact", "suggestion", or "none"
    """
    query_str = str(query).strip()
    query_lower = query_str.lower()

    # --- 0: MANUAL OVERRIDES (The "Colloquialism" Fix) ---
    # Check if the user typed a known abbreviation like "CULC"
    if query_lower in CUSTOM_ALIASES:
        target_name = CUSTOM_ALIASES[query_lower]
        # Find the row that matches this target name exactly
        # We use .str.contains in case the official name in DB is slightly longer
        alias_match = df[df[NAME_COL].astype(str).str.contains(target_name, case=False, regex=False)]
        
        if not alias_match.empty:
            # Return the first match found
            return "exact", alias_match.iloc[0]
    
    # --- 1. CODE MATCHING (Digits) ---
    if query_str.isdigit():
        # Reject codes longer than 3 digits immediately
        if len(query_str) > 3:
            return "none", []
            
        # Exact or Padded Match (e.g. "77" -> "077")
        padded_code = query_str.zfill(3)
        code_match = df[df[CODE_COL].astype(str) == padded_code]
        
        if not code_match.empty:
            return "exact", code_match.iloc[0]
        
        # If it's a 3-digit number but doesn't exist, don't try to fuzzy match names. 
        # "999" shouldn't match "Building 9" unless you really want it to.
        return "none", []

    # --- 2. NAME MATCHING (Strings) ---
    
    # 2a. Exact Match
    exact_match = df[df[NAME_COL].astype(str).str.lower() == query_lower]
    if not exact_match.empty:
        return "exact", exact_match.iloc[0]

    # 2b. Substring Match (High Confidence)
    # e.g. "Skiles" matches "Skiles Classroom Building"
    substring_matches = df[df[NAME_COL].astype(str).str.lower().str.contains(query_lower, regex=False)]
    if not substring_matches.empty:
        # Pick shortest name (most precise)
        best_idx = substring_matches[NAME_COL].astype(str).str.len().idxmin()
        return "exact", substring_matches.loc[best_idx]

    # 2c. Fuzzy Match (The "Did you mean?" Logic)
    df = df.copy()
    df['match_score'] = df[NAME_COL].astype(str).apply(
        lambda x: jellyfish.jaro_winkler_similarity(query_lower, x.lower())
    )
    
    # Sort by score (Highest first)
    sorted_matches = df.sort_values(by='match_score', ascending=False)
    best_match = sorted_matches.iloc[0]
    best_score = best_match['match_score']
    
    # THRESHOLDS:
    # > 0.90: Almost perfect match (Small typo: "Skilles" -> "Skiles") -> Auto Zoom
    # 0.60 - 0.90: Ambiguous or "Gibberish-ish" -> Return Suggestions
    # < 0.60: Total gibberish -> No Match
    
    if best_score >= 0.90:
        return "exact", best_match
    
    if best_score >= 0.60:
        # Return Top 3 for "Did you mean?"
        top_3 = sorted_matches.head(3)
        return "suggestion", top_3
        
    return "none", []

@app.get("/search")
def search_building(q: str):
    if db["campus"] is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    campus = db["campus"]
    match_type, result = find_building_match(q, campus)
    
    if match_type == "exact":
        # Auto-Zoom
        centroid = result.geometry.centroid
        return {
            "type": "exact",
            "data": {
                "name": result[NAME_COL],
                "code": result[CODE_COL],
                "lat": centroid.y,
                "lon": centroid.x
            }
        }
        
    elif match_type == "suggestion":
        # Return list of options
        suggestions = []
        for _, row in result.iterrows():
            suggestions.append({
                "name": row[NAME_COL],
                "code": row[CODE_COL]
            })
        return {
            "type": "suggestions",
            "message": f"No exact match for '{q}'. Did you mean:",
            "data": suggestions
        }
        
    else:
        raise HTTPException(status_code=404, detail="No building match found.")