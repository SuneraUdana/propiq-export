import random, json
from datetime import datetime, timedelta

SUBURBS = ["Fitzroy","Richmond","Hawthorn","Brunswick","South Yarra",
           "Collingwood","St Kilda","Northcote","Prahran","Footscray"]
STREETS = ["Smith St","Brunswick St","Johnston St","Victoria St","Church St",
           "High St","Park St","Queen St","King St","George St"]
TYPES   = ["house","unit","townhouse"]
AGENTS  = [("James Wilson","0412 345 678","Ray White"),
           ("Sarah Chen","0423 456 789","McGrath"),
           ("Michael Brown","0434 567 890","Jellis Craig"),
           ("Emma Davis","0445 678 901","Marshall White")]

def simulate_listings(n=399):
    random.seed(42)
    records = []
    base = datetime.now() - timedelta(days=180)
    for i in range(n):
        sub   = random.choice(SUBURBS)
        ptype = random.choice(TYPES)
        beds  = random.randint(2,5) if ptype=="house" else random.randint(1,3)
        price = random.randint(600000, 3200000)
        land  = random.randint(120,800) if ptype in ["house","townhouse"] else None
        ag    = random.choice(AGENTS)
        sold  = (base + timedelta(days=random.randint(0,180))).strftime("%Y-%m-%d")
        records.append({
            "address":       f"{random.randint(1,200)} {random.choice(STREETS)}",
            "suburb":        sub,
            "state":         "VIC",
            "postcode":      str(3000 + SUBURBS.index(sub)),
            "sale_price":    price,
            "land_size_sqm": land,
            "house_type":    ptype,
            "year_built":    random.randint(1960,2020),
            "bedrooms":      beds,
            "bathrooms":     random.randint(1,beds-1) if beds>1 else 1,
            "agent_name":    ag[0],
            "agent_phone":   ag[1],
            "agency":        ag[2],
            "image_urls":    json.dumps([]),
            "listing_url":   "",
            "source":        "simulator",
            "sold_date":     sold,
        })
    return records


def clean_records(records):
    for r in records:
        r["sale_price"]    = float(r.get("sale_price") or 0)
        r["land_size_sqm"] = float(r["land_size_sqm"]) if r.get("land_size_sqm") else 0.0
        r["bedrooms"]      = int(r.get("bedrooms") or 2)
        r["bathrooms"]     = int(r.get("bathrooms") or 1)
        r["year_built"]    = int(r.get("year_built") or 1990)
        r["suburb"]        = (r.get("suburb") or "Unknown").strip().title()
        r["house_type"]    = (r.get("house_type") or "house").lower()
        r["address"]       = (r.get("address") or "").strip()
        r["postcode"]      = str(r.get("postcode") or "").strip()
        r["agent_name"]    = (r.get("agent_name") or "").strip()
        r["agent_phone"]   = (r.get("agent_phone") or "").strip()
        r["source"]        = r.get("source", "unknown")
        if "listing_id" not in r:
            r["listing_id"] = r["address"] + "_" + r["suburb"]
    return [r for r in records if r["sale_price"] > 0 and r["address"]]
