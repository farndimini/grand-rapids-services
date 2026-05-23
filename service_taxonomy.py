"""
service_taxonomy.py — Comprehensive Service Taxonomy for Grand Rapids

The brain of the expansion engine. Defines 20+ home service niches with:
aliases, sub-services, pain points, seasonality, brands, FAQ patterns, CTAs.

Usage:
    from service_taxonomy import SERVICE_TAXONOMY, get_service, list_services
"""

from typing import Any

SERVICE_TAXONOMY: dict[str, dict[str, Any]] = {
    # ════════════════════════════════════════════
    # PLUMBING
    # ════════════════════════════════════════════
    "plumbing": {
        "label": "Plumbing",
        "category": "Home Services",
        "hub_slug": "plumbing-services-grand-rapids",
        "hub_title": "Plumbing Services in Grand Rapids, MI",
        "aliases": ["plumber", "plumbing contractor", "pipe repair", "plumbing service", "24 hour plumber"],
        "modifier_relevance": {"emergency": 10, "24-hour": 10, "same-day": 9, "affordable": 7, "near-me": 8},
        "service_items": [
            "Pipe Repair & Replacement", "Water Heater Installation", "Toilet Repair",
            "Faucet Installation", "Drain Cleaning", "Sewer Line Repair",
            "Leak Detection", "Water Softener Installation", "Garbage Disposal Repair",
            "Sump Pump Installation",
        ],
        "subservices": {
            "water-heater-repair": {"label": "Water Heater Repair", "keywords": ["water heater repair", "water heater replacement", "hot water heater", "tankless water heater"]},
            "drain-cleaning": {"label": "Drain Cleaning", "keywords": ["drain cleaning", "clogged drain", "drain unclogging", "hydro jetting"]},
            "sewer-line-repair": {"label": "Sewer Line Repair", "keywords": ["sewer line repair", "sewer replacement", "sewer camera inspection", "trenchless sewer"]},
            "leak-detection": {"label": "Leak Detection", "keywords": ["leak detection", "water leak", "slab leak", "pipe leak repair"]},
            "toilet-repair": {"label": "Toilet Repair", "keywords": ["toilet repair", "toilet replacement", "running toilet", "clogged toilet"]},
            "frozen-pipe-repair": {"label": "Frozen Pipe Repair", "keywords": ["frozen pipe", "burst pipe", "pipe thawing", "frozen pipe repair"]},
            "water-softener": {"label": "Water Softener Installation", "keywords": ["water softener", "water filtration", "hard water treatment", "whole house filter"]},
            "sump-pump": {"label": "Sump Pump Repair", "keywords": ["sump pump repair", "sump pump installation", "basement flooding", "backup sump pump"]},
        },
        "brands": ["Rheem", "Bradford White", "AO Smith", "Delta", "Moen", "Kohler", "American Standard", "RIDGID"],
        "pain_points": ["burst pipes in winter", "no hot water", "water damage from leaks", "sewer backups", "high water bills from leaks", "frozen pipes in Michigan winters"],
        "seasonality": {"peak": ["winter"], "high": ["fall", "spring"], "low": ["summer"]},
        "emergency_keywords": ["emergency plumber", "burst pipe repair", "flooded basement", "sewer backup emergency"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Prices vary by service. Water heater replacement averages $800-$1,500. Drain cleaning starts at $150."),
            ("Do you offer emergency {service} in Grand Rapids?", "Yes, we provide 24/7 emergency plumbing service throughout Grand Rapids and all of Kent County."),
            ("Are your {service} technicians licensed in Michigan?", "All our plumbing technicians are fully licensed by the State of Michigan."),
        ],
        "cta": "Call now for emergency plumbing in Grand Rapids",
        "cta_sub": "24/7 emergency service · Licensed plumbers · Upfront pricing",
        "response_time": "30-60 minutes for emergencies",
        "service_call": "$79-$129",
    },

    # ════════════════════════════════════════════
    # HVAC
    # ════════════════════════════════════════════
    "hvac": {
        "label": "HVAC",
        "category": "Heating & Cooling",
        "hub_slug": "hvac-services-grand-rapids",
        "hub_title": "HVAC Services in Grand Rapids, MI",
        "aliases": ["heating and cooling", "hvac contractor", "ac repair", "furnace repair", "hvac service"],
        "modifier_relevance": {"emergency": 10, "24-hour": 9, "same-day": 8, "affordable": 7, "near-me": 7},
        "service_items": [
            "AC Installation", "Furnace Repair", "Heat Pump Service", "Duct Cleaning",
            "Thermostat Installation", "Boiler Repair", "Air Quality Systems",
            "Mini-Split Installation", "Commercial HVAC", "Emergency HVAC",
        ],
        "subservices": {
            "ac-repair": {"label": "AC Repair", "keywords": ["ac repair", "air conditioning repair", "central ac service", "ac not cooling"]},
            "furnace-repair": {"label": "Furnace Repair", "keywords": ["furnace repair", "furnace replacement", "heating repair", "furnace not working"]},
            "heat-pump": {"label": "Heat Pump Service", "keywords": ["heat pump repair", "heat pump installation", "mini split service", "ductless heat pump"]},
            "duct-cleaning": {"label": "Duct Cleaning", "keywords": ["duct cleaning", "air duct cleaning", "dryer vent cleaning", "hvac duct repair"]},
            "boiler-repair": {"label": "Boiler Repair", "keywords": ["boiler repair", "boiler replacement", "steam boiler service", "hydronic heating"]},
            "thermostat": {"label": "Thermostat Installation", "keywords": ["smart thermostat", "thermostat installation", "nest installation", "ecobee setup"]},
        },
        "brands": ["Carrier", "Trane", "Lennox", "Rheem", "Goodman", "Bryant", "York", "American Standard"],
        "pain_points": ["furnace failure in Michigan winter", "AC broken during heat wave", "high energy bills", "uneven heating/cooling", "poor indoor air quality"],
        "seasonality": {"peak": ["winter", "summer"], "high": ["fall", "spring"], "low": []},
        "emergency_keywords": ["emergency hvac", "no heat emergency", "ac emergency repair", "furnace emergency"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Furnace repair averages $200-$600. AC repair averages $150-$500. Full replacements range $3,000-$8,000."),
            ("Do you offer 24-hour {service} in Grand Rapids?", "Yes, HVAC emergencies don't wait. We offer 24/7 heating and cooling service across Grand Rapids."),
            ("Are your HVAC technicians certified?", "All technicians are NATE-certified with ongoing training on the latest systems."),
        ],
        "cta": "Call now for HVAC service in Grand Rapids",
        "cta_sub": "24/7 emergency service · NATE-certified · Upfront pricing",
        "response_time": "1-2 hours for emergencies",
        "service_call": "$89-$149",
    },

    # ════════════════════════════════════════════
    # ELECTRICAL
    # ════════════════════════════════════════════
    "electrical": {
        "label": "Electrical",
        "category": "Home Services",
        "hub_slug": "electrical-services-grand-rapids",
        "hub_title": "Electrical Services in Grand Rapids, MI",
        "aliases": ["electrician", "electrical contractor", "electrical repair", "licensed electrician", "commercial electrician"],
        "modifier_relevance": {"emergency": 10, "24-hour": 10, "same-day": 8, "affordable": 7, "near-me": 8},
        "service_items": [
            "Panel Upgrades", "Wiring Repair", "Outlet Installation", "Lighting Installation",
            "Ceiling Fan Installation", "Generator Installation", "EV Charger Installation",
            "Smoke Detector Installation", "Home Rewiring", "Electrical Inspection",
        ],
        "subservices": {
            "panel-upgrade": {"label": "Electrical Panel Upgrade", "keywords": ["electrical panel upgrade", "breaker panel", "fuse box upgrade", "200 amp service"]},
            "wiring-repair": {"label": "Wiring Repair", "keywords": ["electrical wiring", "home rewiring", "wiring repair", "old wiring replacement"]},
            "generator-installation": {"label": "Generator Installation", "keywords": ["generator installation", "standby generator", "whole house generator", "portable generator"]},
            "ev-charger": {"label": "EV Charger Installation", "keywords": ["ev charger installation", "tesla charger", "electric car charger", "level 2 charger"]},
            "lighting-installation": {"label": "Lighting Installation", "keywords": ["lighting installation", "recessed lighting", "outdoor lighting", "landscape lighting"]},
            "ceiling-fan": {"label": "Ceiling Fan Installation", "keywords": ["ceiling fan installation", "ceiling fan replacement", "ceiling fan repair"]},
        },
        "brands": ["Leviton", "Square D", "Eaton", "GE", "Siemens", "Generac", "ChargerPoint", "Kichler"],
        "pain_points": ["flickering lights", "frequent breaker trips", "old aluminum wiring", "no generator for power outages", "outdated electrical panels"],
        "seasonality": {"peak": ["winter"], "high": ["fall", "summer"], "low": ["spring"]},
        "emergency_keywords": ["emergency electrician", "power outage repair", "electrical emergency", "sparking outlet"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Panel upgrades average $1,500-$3,000. EV charger installation $500-$2,000. Standard repairs $150-$500."),
            ("Do you offer emergency electrical service?", "Yes, we provide 24/7 emergency electrical service throughout Grand Rapids and Kent County."),
            ("Are your electricians licensed in Grand Rapids?", "All our electricians are licensed by the State of Michigan and fully insured."),
        ],
        "cta": "Call now for electrical service in Grand Rapids",
        "cta_sub": "24/7 emergency service · Licensed electricians · Upfront pricing",
        "response_time": "1 hour for emergencies",
        "service_call": "$85-$149",
    },

    # ════════════════════════════════════════════
    # ROOFING
    # ════════════════════════════════════════════
    "roofing": {
        "label": "Roofing",
        "category": "Exterior Services",
        "hub_slug": "roofing-services-grand-rapids",
        "hub_title": "Roofing Services in Grand Rapids, MI",
        "aliases": ["roofer", "roofing contractor", "roof repair", "roof replacement", "metal roofing"],
        "modifier_relevance": {"emergency": 10, "24-hour": 7, "same-day": 6, "affordable": 8, "near-me": 7},
        "service_items": [
            "Roof Repair", "Roof Replacement", "Metal Roofing", "Shingle Installation",
            "Flat Roof Repair", "Gutter Installation", "Skylight Installation",
            "Ice Dam Removal", "Roof Inspection", "Storm Damage Repair",
        ],
        "subservices": {
            "roof-repair": {"label": "Roof Repair", "keywords": ["roof repair", "leaky roof repair", "shingle repair", "roof leak"]},
            "roof-replacement": {"label": "Roof Replacement", "keywords": ["roof replacement", "new roof", "complete roof replacement", "reroofing"]},
            "metal-roofing": {"label": "Metal Roofing", "keywords": ["metal roofing", "steel roof", "standing seam", "metal roof installation"]},
            "storm-damage": {"label": "Storm Damage Repair", "keywords": ["storm damage repair", "hail damage roof", "wind damage roof", "insurance roof claim"]},
            "ice-dam-removal": {"label": "Ice Dam Removal", "keywords": ["ice dam removal", "ice dam prevention", "roof ice removal", "winter roof damage"]},
            "gutter-installation": {"label": "Gutter Installation", "keywords": ["gutter installation", "gutter replacement", "seamless gutters", "leaf guard gutters"]},
        },
        "brands": ["CertainTeed", "GAF", "Owens Corning", "IKO", "Tamko", "Atlas", "BP", "Metal Sales"],
        "pain_points": ["roof leaks during Michigan rain", "ice dams in winter", "storm damage from hail", "high energy bills from poor insulation", "old aging roof"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": ["emergency roof repair", "leaky roof emergency", "storm damage roof", "roof leak repair"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Roof repair averages $500-$1,500. Complete roof replacement $5,000-$15,000 depending on size and materials."),
            ("Do you offer free roof inspections?", "Yes, we provide free roof inspections and estimates for Grand Rapids homeowners."),
            ("Are you licensed and insured for roofing in Michigan?", "Yes, we are fully licensed, bonded, and insured for all roofing work in Michigan."),
        ],
        "cta": "Get a free roof inspection in Grand Rapids",
        "cta_sub": "Free estimates · Licensed roofers · Storm damage specialists",
        "response_time": "24-48 hours for inspections",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # WATER DAMAGE RESTORATION
    # ════════════════════════════════════════════
    "water damage restoration": {
        "label": "Water Damage Restoration",
        "category": "Restoration Services",
        "hub_slug": "water-damage-restoration-grand-rapids",
        "hub_title": "Water Damage Restoration in Grand Rapids, MI",
        "aliases": ["water damage cleanup", "flood damage repair", "water restoration", "water extraction", "flood cleanup"],
        "modifier_relevance": {"emergency": 10, "24-hour": 10, "same-day": 9, "affordable": 6, "near-me": 8},
        "service_items": [
            "Water Extraction", "Flood Damage Repair", "Basement Waterproofing",
            "Mold Remediation", "Structural Drying", "Sewage Cleanup",
            "Crawlspace Drying", "Dehumidification", "Contents Restoration",
        ],
        "subservices": {
            "water-extraction": {"label": "Water Extraction", "keywords": ["water extraction", "water removal", "standing water removal", "flood water extraction"]},
            "basement-waterproofing": {"label": "Basement Waterproofing", "keywords": ["basement waterproofing", "wet basement repair", "foundation waterproofing", "interior waterproofing"]},
            "sewage-cleanup": {"label": "Sewage Cleanup", "keywords": ["sewage cleanup", "sewer backup cleanup", "biohazard cleanup", "sewage damage restoration"]},
            "flood-damage": {"label": "Flood Damage Repair", "keywords": ["flood damage repair", "flood restoration", "flooded basement cleanup", "flood damage restoration"]},
            "structural-drying": {"label": "Structural Drying", "keywords": ["structural drying", "wall drying", "floor drying", "commercial drying services"]},
        },
        "brands": ["Dri-Eaz", "Phoenix", "AlorAir", "Sapphire", "Injectidry", "BlueDri"],
        "pain_points": ["flooded basement after heavy rain", "burst pipe water damage", "sewer backup in basement", "mold growth after water leak", "crawlspace flooding"],
        "seasonality": {"peak": ["spring", "summer"], "high": ["winter", "fall"], "low": []},
        "emergency_keywords": ["emergency water damage", "flood emergency", "water damage restoration", "basement flooding emergency"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Water extraction starts at $300-$600. Full flood damage restoration averages $2,000-$8,000 depending on severity."),
            ("Do you offer 24/7 emergency water damage service?", "Yes, water damage emergencies require immediate response. We're available 24/7."),
            ("How quickly can you respond to water damage in Grand Rapids?", "We aim for 60-minute response time for all water damage emergencies in Grand Rapids."),
        ],
        "cta": "Call now for water damage emergency in Grand Rapids",
        "cta_sub": "24/7 emergency response · 60-minute arrival · Insurance claims help",
        "response_time": "Under 1 hour for emergencies",
        "service_call": "Free inspection",
    },

    # ════════════════════════════════════════════
    # MOLD REMEDIATION
    # ════════════════════════════════════════════
    "mold remediation": {
        "label": "Mold Remediation",
        "category": "Restoration Services",
        "hub_slug": "mold-remediation-grand-rapids",
        "hub_title": "Mold Remediation Services in Grand Rapids, MI",
        "aliases": ["mold removal", "mold inspection", "black mold removal", "mold testing", "mold abatement"],
        "modifier_relevance": {"emergency": 9, "24-hour": 7, "same-day": 7, "affordable": 7, "near-me": 8},
        "service_items": [
            "Mold Inspection", "Black Mold Removal", "Attic Mold Remediation",
            "Basement Mold Removal", "Crawlspace Mold Treatment", "Air Quality Testing",
            "Mold Prevention", "HVAC Mold Cleaning", "Dry Rot Repair",
        ],
        "subservices": {
            "mold-inspection": {"label": "Mold Inspection", "keywords": ["mold inspection", "mold testing", "mold detection", "black mold testing"]},
            "black-mold-removal": {"label": "Black Mold Removal", "keywords": ["black mold removal", "toxic mold removal", "stachybotrys removal", "mold abatement"]},
            "attic-mold": {"label": "Attic Mold Remediation", "keywords": ["attic mold removal", "attic mold remediation", "roof mold treatment"]},
            "crawlspace-mold": {"label": "Crawlspace Mold Treatment", "keywords": ["crawlspace mold", "crawlspace remediation", "vapor barrier installation"]},
        },
        "brands": ["Concrobium", "RMR-86", "Foster 40-80", "Benefect", "Microban", "Sporicidin"],
        "pain_points": ["black mold in basement", "musty odors", "health concerns from mold", "mold after water damage", "mold in bathrooms and attics"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": ["emergency mold removal", "mold emergency", "toxic mold", "mold damage"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Mold inspection averages $300-$600. Remediation ranges $1,500-$6,000 depending on the extent of contamination."),
            ("Do you test for mold before removal?", "Yes, we conduct thorough mold testing and air quality assessments before beginning any remediation work."),
            ("Are your mold remediation technicians certified?", "All our technicians are IICRC-certified in mold remediation and follow EPA guidelines."),
        ],
        "cta": "Schedule a mold inspection in Grand Rapids",
        "cta_sub": "Free inspections · IICRC-certified · Safe removal guaranteed",
        "response_time": "24-48 hours",
        "service_call": "Free inspection",
    },

    # ════════════════════════════════════════════
    # FLOORING
    # ════════════════════════════════════════════
    "flooring": {
        "label": "Flooring",
        "category": "Home Improvement",
        "hub_slug": "flooring-services-grand-rapids",
        "hub_title": "Flooring Services in Grand Rapids, MI",
        "aliases": ["flooring contractor", "floor installation", "hardwood flooring", "carpet installation", "flooring company"],
        "modifier_relevance": {"emergency": 2, "24-hour": 2, "same-day": 3, "affordable": 8, "near-me": 7},
        "service_items": [
            "Hardwood Flooring", "Laminate Flooring", "Luxury Vinyl Plank",
            "Carpet Installation", "Tile Flooring", "Engineered Wood",
            "Floor Refinishing", "Staircase Carpet", "Commercial Flooring",
        ],
        "subservices": {
            "hardwood-flooring": {"label": "Hardwood Flooring", "keywords": ["hardwood flooring", "solid hardwood", "engineered hardwood", "hardwood installation"]},
            "laminate-flooring": {"label": "Laminate Flooring", "keywords": ["laminate flooring", "laminate installation", "waterproof laminate", "pergo flooring"]},
            "vinyl-plank": {"label": "Luxury Vinyl Plank", "keywords": ["luxury vinyl plank", "lvp flooring", "vinyl plank flooring", "waterproof vinyl"]},
            "carpet-installation": {"label": "Carpet Installation", "keywords": ["carpet installation", "carpet replacement", "carpet padding", "stair carpet"]},
            "floor-refinishing": {"label": "Floor Refinishing", "keywords": ["floor refinishing", "hardwood refinishing", "sand and finish", "floor restoration"]},
            "tile-flooring": {"label": "Tile Flooring", "keywords": ["tile flooring", "ceramic tile", "porcelain tile", "floor tile installation"]},
        },
        "brands": ["Shaw", "Mohawk", "Anderson Tuftex", "Armstrong", "Pergo", "Coretec", "Mannington", "Karastan"],
        "pain_points": ["worn out carpet", "scratched hardwood", "outdated flooring", "pet damage on floors", "high humidity affecting floors"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Hardwood flooring averages $8-$15/sq ft installed. LVP $4-$8/sq ft. Carpet $3-$7/sq ft."),
            ("Do you offer free flooring estimates?", "Yes, we provide free in-home measurements and estimates with no obligation."),
            ("How long does {sub} take in Grand Rapids?", "Most flooring projects are completed in 1-5 days depending on the size of the area."),
        ],
        "cta": "Get a free flooring estimate in Grand Rapids",
        "cta_sub": "Free estimates · Expert installation · All major brands",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # WINDOW REPLACEMENT
    # ════════════════════════════════════════════
    "window replacement": {
        "label": "Window Replacement",
        "category": "Home Improvement",
        "hub_slug": "window-replacement-grand-rapids",
        "hub_title": "Window Replacement in Grand Rapids, MI",
        "aliases": ["windows", "window installation", "energy efficient windows", "new windows", "vinyl windows"],
        "modifier_relevance": {"emergency": 3, "24-hour": 1, "same-day": 2, "affordable": 8, "near-me": 7},
        "service_items": [
            "Vinyl Window Installation", "Wood Window Replacement", "Energy-Efficient Windows",
            "Bay Window Installation", "Casement Windows", "Sliding Windows",
            "Double-Hung Windows", "Picture Windows", "Storm Window Installation",
        ],
        "subservices": {
            "vinyl-windows": {"label": "Vinyl Window Installation", "keywords": ["vinyl windows", "vinyl window replacement", "white vinyl windows", "custom vinyl windows"]},
            "energy-efficient": {"label": "Energy Efficient Windows", "keywords": ["energy efficient windows", "low-e windows", "argon gas windows", "energy star windows"]},
            "bay-windows": {"label": "Bay Window Installation", "keywords": ["bay window installation", "bow window", "garden window", "bay window replacement"]},
            "storm-windows": {"label": "Storm Window Installation", "keywords": ["storm windows", "storm window installation", "impact windows", "protective windows"]},
            "custom-windows": {"label": "Custom Window Installation", "keywords": ["custom windows", "custom size windows", "arched windows", "specialty windows"]},
        },
        "brands": ["Andersen", "Pella", "Marvin", "Jeld-Wen", "Simonton", "Milgard", "CertainTeed", "Harvey"],
        "pain_points": ["drafty windows in winter", "high energy bills", "condensation between panes", "difficult to open windows", "old single-pane windows"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Average window replacement costs $400-$1,200 per window installed. Energy-efficient upgrades may qualify for tax credits."),
            ("Do you offer free window estimates?", "Yes, we provide free in-home consultations and detailed estimates."),
            ("Are your windows Energy Star certified?", "Yes, we offer Energy Star certified windows that can reduce your energy bills significantly."),
        ],
        "cta": "Schedule a free window consultation in Grand Rapids",
        "cta_sub": "Free estimates · Energy Star certified · Professional installation",
        "response_time": "Scheduled within 1-2 weeks",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # SIDING
    # ════════════════════════════════════════════
    "siding": {
        "label": "Siding",
        "category": "Exterior Services",
        "hub_slug": "siding-services-grand-rapids",
        "hub_title": "Siding Services in Grand Rapids, MI",
        "aliases": ["siding contractor", "siding installation", "vinyl siding", "fiber cement siding", "exterior siding"],
        "modifier_relevance": {"emergency": 4, "24-hour": 1, "same-day": 2, "affordable": 8, "near-me": 7},
        "service_items": [
            "Vinyl Siding", "Fiber Cement Siding", "Wood Siding", "Insulated Siding",
            "Siding Repair", "Soffit Installation", "Fascia Repair", "Trim Installation",
        ],
        "subservices": {
            "vinyl-siding": {"label": "Vinyl Siding Installation", "keywords": ["vinyl siding", "vinyl siding installation", "vinyl siding replacement", "insulated vinyl siding"]},
            "fiber-cement": {"label": "Fiber Cement Siding", "keywords": ["fiber cement siding", "hardie board", "cement board siding", "james hardie siding"]},
            "siding-repair": {"label": "Siding Repair", "keywords": ["siding repair", "siding replacement", "damaged siding repair", "hole in siding repair"]},
            "soffit-fascia": {"label": "Soffit & Fascia Installation", "keywords": ["soffit installation", "fascia repair", "soffit replacement", "eaves repair"]},
        },
        "brands": ["James Hardie", "CertainTeed", "Mastic", "Norandex", "Georgia-Pacific", "Louisiana-Pacific", "KWP"],
        "pain_points": ["cracked or warped siding", "high energy bills from poor insulation", "faded exterior paint", "wood rot on trim", "Michigan winter damage to siding"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Vinyl siding averages $4-$9/sq ft installed. Fiber cement $7-$14/sq ft. Free estimates available."),
            ("How long does siding installation take?", "Most residential siding projects are completed in 3-7 days depending on home size."),
            ("Does new siding improve energy efficiency?", "Yes, insulated siding can significantly reduce heating and cooling costs in Michigan homes."),
        ],
        "cta": "Get a free siding estimate in Grand Rapids",
        "cta_sub": "Free estimates · Lifetime warranties · Professional installation",
        "response_time": "Scheduled within 1-2 weeks",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # CONCRETE
    # ════════════════════════════════════════════
    "concrete": {
        "label": "Concrete",
        "category": "Exterior Services",
        "hub_slug": "concrete-services-grand-rapids",
        "hub_title": "Concrete Services in Grand Rapids, MI",
        "aliases": ["concrete contractor", "concrete driveway", "stamped concrete", "concrete patio", "concrete repair"],
        "modifier_relevance": {"emergency": 4, "24-hour": 1, "same-day": 2, "affordable": 8, "near-me": 7},
        "service_items": [
            "Concrete Driveways", "Stamped Concrete", "Concrete Patios", "Concrete Walkways",
            "Foundation Repair", "Concrete Steps", "Garage Floor Coating",
            "Retaining Walls", "Commercial Concrete",
        ],
        "subservices": {
            "concrete-driveway": {"label": "Concrete Driveway", "keywords": ["concrete driveway", "driveway replacement", "driveway installation", "concrete driveway repair"]},
            "stamped-concrete": {"label": "Stamped Concrete", "keywords": ["stamped concrete", "decorative concrete", "patterned concrete", "colored concrete"]},
            "concrete-patio": {"label": "Concrete Patio", "keywords": ["concrete patio", "patio installation", "outdoor concrete", "concrete slab patio"]},
            "foundation-repair": {"label": "Foundation Repair", "keywords": ["foundation repair", "foundation crack repair", "foundation leveling", "concrete foundation"]},
            "garage-floor": {"label": "Garage Floor Coating", "keywords": ["garage floor coating", "epoxy garage floor", "garage floor finishing", "polyurea coating"]},
        },
        "brands": ["Quikrete", "Sakrete", "BASF", "Sika", "Rust-Oleum", "Polymer Solutions"],
        "pain_points": ["cracked driveway", "uneven concrete walkways", "spalling concrete from salt", "old worn-out garage floor", "foundation cracks"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": ["emergency foundation repair", "concrete hazard repair"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Concrete driveways average $6-$12/sq ft. Stamped concrete $10-$18/sq ft. Garage floor coating $3-$7/sq ft."),
            ("Do you offer free concrete estimates?", "Yes, we provide free on-site estimates with detailed quotes."),
            ("How long does concrete work take in Grand Rapids?", "Driveway installation typically takes 3-5 days including curing time."),
        ],
        "cta": "Get a free concrete estimate in Grand Rapids",
        "cta_sub": "Free estimates · Licensed contractors · Quality guaranteed",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # DECK & PATIO
    # ════════════════════════════════════════════
    "deck and patio": {
        "label": "Deck & Patio",
        "category": "Outdoor Living",
        "hub_slug": "deck-patio-services-grand-rapids",
        "hub_title": "Deck & Patio Services in Grand Rapids, MI",
        "aliases": ["deck builder", "deck construction", "patio builder", "composite deck", "porch builder"],
        "modifier_relevance": {"emergency": 2, "24-hour": 1, "same-day": 2, "affordable": 8, "near-me": 7},
        "service_items": [
            "Deck Building", "Composite Decking", "Patio Installation", "Pergola Construction",
            "Screened Porch", "Covered Patio", "Deck Repair", "Railing Installation",
        ],
        "subservices": {
            "deck-building": {"label": "Deck Building", "keywords": ["deck builder", "deck construction", "custom deck", "wood deck installation"]},
            "composite-decking": {"label": "Composite Decking", "keywords": ["composite decking", "trex decking", "timbertech deck", "PVC decking"]},
            "patio-installation": {"label": "Patio Installation", "keywords": ["patio installation", "paver patio", "flagstone patio", "brick patio"]},
            "pergola": {"label": "Pergola Construction", "keywords": ["pergola", "pergola construction", "outdoor covering", "shade structure"]},
            "porch": {"label": "Screened Porch", "keywords": ["screened porch", "porch enclosure", "three season porch", "covered porch"]},
        },
        "brands": ["Trex", "TimberTech", "Fiberon", "Azek", "Deckorators", "MiraTEC", "Weyerhaeuser"],
        "pain_points": ["rotting wood deck", "worn out patio", "cracked concrete patio", "old unlevel deck", "no outdoor living space"],
        "seasonality": {"peak": ["spring", "summer"], "high": ["fall"], "low": ["winter"]},
        "emergency_keywords": ["deck repair emergency", "unsafe deck repair"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Wood deck averages $25-$45/sq ft. Composite decking $40-$65/sq ft. Paver patios $12-$25/sq ft."),
            ("Do you offer free deck design consultations?", "Yes, we provide free design consultations and 3D renderings for your project."),
            ("How long does it take to build a deck?", "Most deck projects are completed in 1-3 weeks depending on size and complexity."),
        ],
        "cta": "Schedule a free deck consultation in Grand Rapids",
        "cta_sub": "Free designs · Licensed contractors · Premium materials",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # KITCHEN REMODELING
    # ════════════════════════════════════════════
    "kitchen remodeling": {
        "label": "Kitchen Remodeling",
        "category": "Home Remodeling",
        "hub_slug": "kitchen-remodeling-grand-rapids",
        "hub_title": "Kitchen Remodeling in Grand Rapids, MI",
        "aliases": ["kitchen remodel", "kitchen renovation", "kitchen contractor", "custom kitchen", "kitchen cabinets"],
        "modifier_relevance": {"emergency": 1, "24-hour": 1, "same-day": 1, "affordable": 8, "near-me": 7},
        "service_items": [
            "Cabinet Installation", "Countertop Replacement", "Kitchen Design",
            "Backsplash Installation", "Kitchen Lighting", "Kitchen Flooring",
            "Kitchen Island Construction", "Pantry Design", "Appliance Installation",
        ],
        "subservices": {
            "cabinets": {"label": "Cabinet Installation", "keywords": ["kitchen cabinets", "cabinet installation", "custom cabinets", "cabinet refacing"]},
            "countertops": {"label": "Countertop Replacement", "keywords": ["countertop replacement", "granite countertops", "quartz countertops", "butcher block countertops"]},
            "backsplash": {"label": "Backsplash Installation", "keywords": ["backsplash installation", "kitchen backsplash", "tile backsplash", "subway tile backsplash"]},
            "kitchen-design": {"label": "Kitchen Design", "keywords": ["kitchen design", "kitchen remodel design", "custom kitchen design", "kitchen layout"]},
        },
        "brands": ["KraftMaid", "Merillat", "Schuler", "Dura Supreme", "Wellborn", "Omega", "Showplace"],
        "pain_points": ["outdated kitchen", "limited counter space", "old cabinets falling apart", "poor kitchen layout", "no kitchen island"],
        "seasonality": {"peak": ["winter", "spring"], "high": ["fall"], "low": ["summer"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Full kitchen remodel averages $15,000-$45,000. Cabinet-only replacement $5,000-$15,000. Countertops $2,000-$5,000."),
            ("How long does a kitchen remodel take?", "Most kitchen remodels take 3-8 weeks depending on the scope of work."),
            ("Do you handle permits for kitchen remodeling?", "Yes, we obtain all necessary permits and ensure code compliance for your project."),
        ],
        "cta": "Schedule a free kitchen design consultation",
        "cta_sub": "Free designs · Licensed contractors · Custom cabinetry",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # BATHROOM REMODELING
    # ════════════════════════════════════════════
    "bathroom remodeling": {
        "label": "Bathroom Remodeling",
        "category": "Home Remodeling",
        "hub_slug": "bathroom-remodeling-grand-rapids",
        "hub_title": "Bathroom Remodeling in Grand Rapids, MI",
        "aliases": ["bathroom remodel", "bathroom renovation", "bathroom contractor", "bathroom design", "full bath remodel"],
        "modifier_relevance": {"emergency": 2, "24-hour": 1, "same-day": 1, "affordable": 8, "near-me": 7},
        "service_items": [
            "Full Bathroom Remodel", "Shower Installation", "Bathtub Replacement",
            "Vanity Installation", "Toilet Replacement", "Bathroom Tile",
            "Bathroom Lighting", "Ventilation Installation", "Accessibility Updates",
        ],
        "subservices": {
            "full-bathroom": {"label": "Full Bathroom Remodel", "keywords": ["bathroom remodel", "full bathroom renovation", "bathroom makeover", "complete bathroom remodel"]},
            "tub-replacement": {"label": "Bathtub Replacement", "keywords": ["bathtub replacement", "soaking tub", "freestanding tub", "alcove tub"]},
            "vanity": {"label": "Vanity Installation", "keywords": ["bathroom vanity", "vanity installation", "double vanity", "custom bathroom vanity"]},
            "accessibility": {"label": "Accessibility Bathroom Updates", "keywords": ["walk in tub", "accessible bathroom", "grab bar installation", "wheelchair accessible bathroom"]},
        },
        "brands": ["Kohler", "Moen", "Delta", "American Standard", "Toto", "Grohe", "Hansgrohe", "James Martin"],
        "pain_points": ["outdated bathroom", "low water pressure", "mold in bathroom", "old tile and grout", "not enough storage"],
        "seasonality": {"peak": ["winter", "spring"], "high": ["fall"], "low": ["summer"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Bathroom remodel averages $8,000-$20,000. Full renovation with layout changes $15,000-$35,000."),
            ("How long does a bathroom remodel take?", "Most bathroom remodels are completed in 2-4 weeks."),
            ("Do you offer free bathroom design consultations?", "Yes, we provide free in-home consultations with 3D design previews."),
        ],
        "cta": "Schedule a free bathroom consultation in Grand Rapids",
        "cta_sub": "Free designs · Licensed contractors · Premium fixtures",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # PAINTING
    # ════════════════════════════════════════════
    "painting": {
        "label": "Painting",
        "category": "Home Improvement",
        "hub_slug": "painting-services-grand-rapids",
        "hub_title": "Painting Services in Grand Rapids, MI",
        "aliases": ["painter", "house painter", "interior painting", "exterior painting", "painting contractor"],
        "modifier_relevance": {"emergency": 2, "24-hour": 1, "same-day": 3, "affordable": 8, "near-me": 7},
        "service_items": [
            "Interior Painting", "Exterior Painting", "Cabinet Painting",
            "Deck Staining", "Wallpaper Removal", "Drywall Repair",
            "Ceiling Painting", "Trim and Baseboard Painting", "Commercial Painting",
        ],
        "subservices": {
            "interior-painting": {"label": "Interior Painting", "keywords": ["interior painting", "interior house painter", "room painting", "wall painting"]},
            "exterior-painting": {"label": "Exterior Painting", "keywords": ["exterior painting", "house exterior painting", "siding painting", "trim painting"]},
            "cabinet-painting": {"label": "Cabinet Painting", "keywords": ["cabinet painting", "cabinet refinishing", "kitchen cabinet painting", "bathroom cabinet painting"]},
            "drywall-repair": {"label": "Drywall Repair", "keywords": ["drywall repair", "drywall installation", "hole in wall repair", "drywall patching"]},
            "deck-staining": {"label": "Deck Staining", "keywords": ["deck staining", "deck sealing", "wood staining", "fence staining"]},
        },
        "brands": ["Sherwin-Williams", "Benjamin Moore", "PPG", "Behr", "Valspar", "Kelly-Moore"],
        "pain_points": ["peeling paint", "outdated wall colors", "scuffed walls", "faded exterior paint", "water stains on ceiling"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": [],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Interior painting averages $2-$6/sq ft. Exterior painting $3-$8/sq ft. Cabinet painting $50-$100 per door."),
            ("Do you offer free painting estimates?", "Yes, we provide detailed written estimates with no obligation."),
            ("How long does interior painting take?", "Most rooms are completed in 1-2 days. Whole house interior typically takes 3-7 days."),
        ],
        "cta": "Get a free painting estimate in Grand Rapids",
        "cta_sub": "Free estimates · Premium paints · Professional painters",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # FENCING
    # ════════════════════════════════════════════
    "fencing": {
        "label": "Fencing",
        "category": "Exterior Services",
        "hub_slug": "fencing-services-grand-rapids",
        "hub_title": "Fencing Services in Grand Rapids, MI",
        "aliases": ["fence contractor", "fence installation", "fence repair", "privacy fence", "wood fence"],
        "modifier_relevance": {"emergency": 4, "24-hour": 2, "same-day": 3, "affordable": 8, "near-me": 7},
        "service_items": [
            "Privacy Fence", "Wood Fence", "Vinyl Fence", "Chain Link Fence",
            "Wrought Iron Fence", "Gate Installation", "Fence Repair", "Pool Fence",
        ],
        "subservices": {
            "privacy-fence": {"label": "Privacy Fence", "keywords": ["privacy fence", "privacy fencing", "6 foot privacy fence", "private fence installation"]},
            "wood-fence": {"label": "Wood Fence", "keywords": ["wood fence", "cedar fence", "picket fence", "wood privacy fence"]},
            "vinyl-fence": {"label": "Vinyl Fence", "keywords": ["vinyl fence", "pvc fence", "white vinyl fence", "maintenance free fence"]},
            "chain-link": {"label": "Chain Link Fence", "keywords": ["chain link fence", "chain link installation", "galvanized fence", "chain link gate"]},
            "fence-repair": {"label": "Fence Repair", "keywords": ["fence repair", "fence replacement", "gate repair", "fence post replacement"]},
        },
        "brands": ["CertainTeed", "Bufftech", "Ameristar", "Master Halco", "Bekaert", "Universal Forest Products"],
        "pain_points": ["old damaged fence", "leaning fence posts", "no privacy in backyard", "rotting wood fence", "neighbor's dogs getting through"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": ["emergency fence repair", "fence storm damage"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Wood fence averages $20-$40/linear ft. Vinyl fence $30-$55/linear ft. Chain link $15-$25/linear ft."),
            ("Do you offer free fence estimates?", "Yes, we provide free on-site estimates with detailed quotes."),
            ("How long does fence installation take?", "Most residential fence projects are completed in 2-5 days."),
        ],
        "cta": "Get a free fence estimate in Grand Rapids",
        "cta_sub": "Free estimates · Licensed contractors · All fence types",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # LANDSCAPING
    # ════════════════════════════════════════════
    "landscaping": {
        "label": "Landscaping",
        "category": "Outdoor Living",
        "hub_slug": "landscaping-services-grand-rapids",
        "hub_title": "Landscaping Services in Grand Rapids, MI",
        "aliases": ["landscaper", "landscape contractor", "lawn care", "landscape design", "yard maintenance"],
        "modifier_relevance": {"emergency": 3, "24-hour": 1, "same-day": 4, "affordable": 8, "near-me": 7},
        "service_items": [
            "Landscape Design", "Lawn Installation", "Retaining Walls", "Mulch Installation",
            "Tree Trimming", "Shrub Planting", "Irrigation Systems", "Outdoor Lighting",
            "Sod Installation", "French Drain Installation",
        ],
        "subservices": {
            "landscape-design": {"label": "Landscape Design", "keywords": ["landscape design", "landscape architecture", "garden design", "front yard landscaping"]},
            "retaining-walls": {"label": "Retaining Walls", "keywords": ["retaining wall", "segmental retaining wall", "block wall", "landscape wall"]},
            "irrigation": {"label": "Irrigation System Installation", "keywords": ["irrigation system", "sprinkler system", "lawn sprinklers", "drip irrigation"]},
            "tree-trimming": {"label": "Tree Trimming", "keywords": ["tree trimming", "tree pruning", "tree removal", "stump grinding"]},
            "outdoor-lighting": {"label": "Outdoor Lighting", "keywords": ["outdoor lighting", "landscape lighting", "path lighting", "low voltage lighting"]},
            "french-drain": {"label": "French Drain Installation", "keywords": ["french drain", "yard drainage", "water drainage", "yard grading"]},
        },
        "brands": ["John Deere", "Stihl", "Echo", "Husqvarna", "Toro", "Rain Bird", "Hunter"],
        "pain_points": ["poor yard drainage", "dying lawn", "overgrown landscaping", "no curb appeal", "erosion in yard"],
        "seasonality": {"peak": ["spring", "summer"], "high": ["fall"], "low": ["winter"]},
        "emergency_keywords": ["emergency tree removal", "storm damage cleanup"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Landscape design $500-$2,500. Retaining walls $30-$60/sq ft. Irrigation systems $2,000-$5,000."),
            ("Do you offer free landscaping consultations?", "Yes, we provide free on-site consultations and design concepts."),
            ("What landscaping services do you offer in Grand Rapids?", "We offer full-service landscaping from design to installation and maintenance."),
        ],
        "cta": "Schedule a free landscaping consultation",
        "cta_sub": "Free consultations · Custom designs · Quality materials",
        "response_time": "Scheduled within 1 week",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # TREE SERVICE
    # ════════════════════════════════════════════
    "tree service": {
        "label": "Tree Service",
        "category": "Outdoor Services",
        "hub_slug": "tree-services-grand-rapids",
        "hub_title": "Tree Services in Grand Rapids, MI",
        "aliases": ["tree removal", "tree trimming", "arborist", "tree cutting", "stump removal"],
        "modifier_relevance": {"emergency": 10, "24-hour": 9, "same-day": 8, "affordable": 7, "near-me": 7},
        "service_items": [
            "Tree Removal", "Tree Trimming", "Stump Grinding", "Emergency Tree Service",
            "Tree Pruning", "Storm Damage Cleanup", "Lot Clearing", "Arborist Reports",
        ],
        "subservices": {
            "tree-removal": {"label": "Tree Removal", "keywords": ["tree removal", "dangerous tree removal", "backyard tree removal", "large tree removal"]},
            "stump-grinding": {"label": "Stump Grinding", "keywords": ["stump grinding", "stump removal", "tree stump grinding", "stump removal service"]},
            "storm-cleanup": {"label": "Storm Damage Cleanup", "keywords": ["storm damage cleanup", "fallen tree removal", "storm tree removal", "wind damage cleanup"]},
            "tree-trimming": {"label": "Tree Trimming & Pruning", "keywords": ["tree trimming", "tree pruning", "branch trimming", "tree maintenance"]},
            "lot-clearing": {"label": "Lot Clearing", "keywords": ["lot clearing", "land clearing", "brush removal", "land clearing service"]},
        },
        "brands": ["Stihl", "Husqvarna", "Echo", "Vermeer", "Bandit", "Morbark"],
        "pain_points": ["dangerous leaning tree", "storm damaged tree", "overgrown branches near house", "stump in yard", "tree roots damaging foundation"],
        "seasonality": {"peak": ["spring", "summer"], "high": ["fall"], "low": ["winter"]},
        "emergency_keywords": ["emergency tree removal", "fallen tree", "tree emergency", "storm damage tree"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Tree removal averages $400-$2,000 depending on size. Stump grinding $100-$400."),
            ("Do you offer free tree service estimates?", "Yes, we provide free on-site estimates with no obligation."),
            ("Are your tree service crews insured?", "Yes, we are fully insured and our arborists are certified by the International Society of Arboriculture."),
        ],
        "cta": "Get a free tree service estimate in Grand Rapids",
        "cta_sub": "Free estimates · Certified arborists · Fully insured",
        "response_time": "2-4 hours for emergencies",
        "service_call": "Free estimate",
    },

    # ════════════════════════════════════════════
    # PEST CONTROL
    # ════════════════════════════════════════════
    "pest control": {
        "label": "Pest Control",
        "category": "Home Services",
        "hub_slug": "pest-control-grand-rapids",
        "hub_title": "Pest Control in Grand Rapids, MI",
        "aliases": ["exterminator", "pest removal", "bug exterminator", "termite control", "rodent control"],
        "modifier_relevance": {"emergency": 9, "24-hour": 8, "same-day": 8, "affordable": 7, "near-me": 7},
        "service_items": [
            "Termite Control", "Rodent Removal", "Ant Extermination", "Bed Bug Treatment",
            "Spider Control", "Mosquito Control", "Cockroach Extermination",
            "Wasp Removal", "Wildlife Removal",
        ],
        "subservices": {
            "termite-control": {"label": "Termite Control", "keywords": ["termite control", "termite treatment", "termite inspection", "termite extermination"]},
            "rodent-removal": {"label": "Rodent Removal", "keywords": ["rodent removal", "mouse exterminator", "rat control", "rodent proofing"]},
            "bed-bug": {"label": "Bed Bug Treatment", "keywords": ["bed bug treatment", "bed bug exterminator", "bed bug heat treatment", "bed bug inspection"]},
            "mosquito-control": {"label": "Mosquito Control", "keywords": ["mosquito control", "mosquito treatment", "yard mosquito spray", "tick control"]},
            "wildlife-removal": {"label": "Wildlife Removal", "keywords": ["wildlife removal", "raccoon removal", "squirrel removal", "bat removal"]},
        },
        "brands": ["Terminix", "ORKIN", "Ecolab", "BASF", "Syngenta", "Bayer", "Bell Labs"],
        "pain_points": ["roaches in kitchen", "mice in attic", "ants in bathroom", "termite damage", "bed bugs", "wasps near entry"],
        "seasonality": {"peak": ["summer", "fall"], "high": ["spring"], "low": ["winter"]},
        "emergency_keywords": ["emergency pest control", "bed bug emergency", "wasp emergency"],
        "faq_patterns": [
            ("How much does {sub} cost in Grand Rapids?", "Initial pest control treatment averages $150-$400. Monthly maintenance $40-$80."),
            ("Do you offer free pest inspections?", "Yes, we provide free inspections and customized treatment plans."),
            ("Are your pest control products safe for pets?", "Yes, we use EPA-approved products that are safe for children and pets when applied correctly."),
        ],
        "cta": "Schedule a free pest inspection in Grand Rapids",
        "cta_sub": "Free inspections · Licensed technicians · Pet-friendly treatments",
        "response_time": "24-48 hours, same-day for emergencies",
        "service_call": "$75-$150",
    },
}


# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────

def get_service(key: str) -> dict | None:
    """Get a service definition by key, case-insensitive."""
    key_lower = key.lower().strip()
    for sk, sv in SERVICE_TAXONOMY.items():
        if sk == key_lower:
            return sv
        # Check aliases too
        for alias in sv.get("aliases", []):
            if alias.lower() == key_lower:
                return sv
    return None


def get_services_by_modifier(modifier: str, min_relevance: int = 7) -> list[str]:
    """Get service keys that have high relevance for a given modifier."""
    modifier = modifier.lower().strip()
    result = []
    for sk, sv in SERVICE_TAXONOMY.items():
        relevance = sv.get("modifier_relevance", {}).get(modifier, 0)
        if relevance >= min_relevance:
            result.append(sk)
    return result


def get_services_by_category(category: str) -> list[str]:
    """Get all service keys in a given category."""
    cat_lower = category.lower().strip()
    return [sk for sk, sv in SERVICE_TAXONOMY.items() if sv.get("category", "").lower() == cat_lower]


def list_services() -> list[str]:
    """Return all service keys."""
    return list(SERVICE_TAXONOMY.keys())


def list_categories() -> list[str]:
    """Return unique categories."""
    cats = set()
    for sv in SERVICE_TAXONOMY.values():
        cats.add(sv.get("category", "Other"))
    return sorted(cats)


def get_subservice_keys(service_key: str) -> list[str]:
    """Get all subservice keys for a service."""
    sv = SERVICE_TAXONOMY.get(service_key)
    if not sv:
        return []
    return list(sv.get("subservices", {}).keys())


def get_all_keywords() -> list[str]:
    """Get all unique keywords across all services and subservices."""
    kws = set()
    for sk, sv in SERVICE_TAXONOMY.items():
        # Service-level keywords from aliases
        for alias in sv.get("aliases", []):
            kws.add(alias.lower())
        # Subservice keywords
        for ss_key, ss_data in sv.get("subservices", {}).items():
            for kw in ss_data.get("keywords", []):
                kws.add(kw.lower())
    return sorted(kws)
