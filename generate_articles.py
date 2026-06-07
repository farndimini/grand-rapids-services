"""SEO Article Generator — Professional bulk article generator for Grand Rapids Home Services"""
import json, os, re, sys, time, textwrap
from pathlib import Path

ROOT = Path(r"C:\Users\pc\Desktop\2026\New folder\New folder\AGENT 5\projects\grand_rapids")
ASSETS = ROOT / "assets"
IMAGES = ASSETS / "images"

# ─── SERVICE PROFILES ───────────────────────────────────────────────
SERVICES = {
    "plumbing": {
        "name": "Plumbing",
        "icon": "128679",
        "tag": "PLUMBING SERVICE",
        "cat": "plumbing",
        "pricing": [
            ("Pipe repair", "$250-$650", "$150-$400", "35-60 min"),
            ("Water heater repair", "$300-$1,200", "$200-$700", "40-65 min"),
            ("Drain cleaning", "$150-$450", "$95-$300", "30-50 min"),
            ("Sewer line repair", "$400-$1,500", "$250-$900", "45-90 min"),
            ("Leak detection", "$200-$500", "$120-$350", "30-55 min"),
            ("Toilet repair", "$120-$350", "$85-$200", "25-45 min"),
            ("Faucet installation", "$150-$400", "$100-$250", "30-50 min"),
            ("Gas line repair", "$250-$600", "N/A", "20-40 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} calls in {city} range from $150-$2,000 depending on the issue. Simple repairs run $120-$350 while major pipe work can reach $1,500. We provide upfront pricing before starting any work."),
            ("Do you offer 24/7 {service}?", "Yes. We provide 24/7 {service} across {city} and all of Kent County — including nights, weekends, and holidays. Call {phone} for immediate dispatch."),
            ("Are your technicians licensed?", "All our technicians are licensed in Michigan (LARA), fully insured, and background-checked. License verification available upon request."),
            ("How fast can you get to {city}?", "Average response times range from 25 minutes (downtown) to 75 minutes (outer suburbs). We prioritize emergency calls above all other appointments."),
            ("Do you warranty your work?", "Yes. All repairs carry a 1-year parts and labor warranty. If the same issue recurs within 12 months, we return at no charge."),
            ("Can I prevent {service} emergencies?", "Regular maintenance catches most issues early. We recommend annual inspections, seasonal checks, and addressing minor problems before they escalate."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for nights or weekends?", "No. Our rates are the same whether you call at 2 PM Tuesday or 3 AM Sunday. Many plumbers add 50-100% for after-hours — we don't."),
        ],
        "sdesc": "Professional plumbing services including pipe repair, water heater installation, drain cleaning, sewer line repair, and leak detection.",
        "ldesc": "pipe bursts, water heater failures, clogged drains, sewer backups, and gas line issues",
    },
    "hvac": {
        "name": "HVAC",
        "icon": "127777",
        "tag": "HVAC SERVICE",
        "cat": "hvac",
        "pricing": [
            ("AC repair", "$250-$800", "$150-$500", "35-65 min"),
            ("Furnace repair", "$200-$700", "$120-$450", "30-60 min"),
            ("Heat pump service", "$300-$900", "$180-$550", "40-70 min"),
            ("Duct cleaning", "$200-$600", "$120-$400", "45-90 min"),
            ("Thermostat installation", "$100-$300", "$80-$200", "25-45 min"),
            ("Boiler repair", "$300-$1,000", "$200-$650", "40-75 min"),
            ("AC installation", "$800-$3,500", "$500-$2,500", "60-120 min"),
            ("Furnace installation", "$700-$3,000", "$450-$2,000", "60-120 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} calls in {city} range from $150-$3,500 depending on the issue. AC and furnace repairs run $200-$800 while full installations can reach $3,500. Upfront pricing provided."),
            ("Do you offer 24/7 {service}?", "Yes. We provide 24/7 emergency {service} across {city} and Kent County. Call {phone} for immediate dispatch."),
            ("Are your HVAC technicians certified?", "Yes. All technicians are licensed in Michigan, EPA-certified for refrigerant handling, and background-checked."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs). Emergency calls get priority dispatch."),
            ("Do you warranty HVAC repairs?", "Yes. All repairs carry a 1-year parts and labor warranty. New installations include manufacturer warranties plus our workmanship guarantee."),
            ("Can I prevent HVAC emergencies?", "Regular maintenance is key. Change filters monthly, schedule bi-annual tune-ups, and address unusual noises or odors promptly."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for after-hours?", "No. Our emergency rates are the same 24/7. Many companies add 50-100% for nights and weekends — we don't."),
        ],
        "sdesc": "Professional HVAC services including AC repair, furnace service, heat pump maintenance, duct cleaning, and thermostat installation.",
        "ldesc": "AC failures, furnace breakdowns, heat pump issues, refrigerant leaks, and thermostat malfunctions",
    },
    "electrical": {
        "name": "Electrical",
        "icon": "9889",
        "tag": "ELECTRICAL SERVICE",
        "cat": "electrical",
        "pricing": [
            ("Wiring repair", "$200-$700", "$120-$450", "30-60 min"),
            ("Panel upgrade", "$500-$2,500", "$350-$1,800", "60-120 min"),
            ("Lighting installation", "$100-$400", "$80-$250", "25-50 min"),
            ("Outlet repair", "$100-$250", "$75-$180", "20-40 min"),
            ("Ceiling fan installation", "$150-$350", "$100-$250", "30-50 min"),
            ("Surge protection", "$200-$500", "$150-$350", "30-60 min"),
            ("EV charger installation", "$500-$2,000", "$400-$1,500", "60-90 min"),
            ("Panel repair", "$300-$1,000", "$200-$650", "40-75 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} calls in {city} range from $100-$2,500. Simple outlet repairs run $100-$250 while panel upgrades can reach $2,500. Upfront pricing before work begins."),
            ("Do you offer 24/7 {service}?", "Yes. Emergency electrical service is available 24/7/365 across {city} and Kent County. Call {phone} for immediate dispatch."),
            ("Are your electricians licensed?", "Yes. All electricians are licensed in Michigan, fully insured, and background-checked."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs). Emergency calls prioritized."),
            ("Do you warranty electrical work?", "Yes. All repairs carry a 1-year parts and labor warranty."),
            ("Can I prevent electrical emergencies?", "Schedule annual inspections, avoid overloading circuits, and replace outdated wiring. Signs like flickering lights or warm outlets need immediate attention."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for after-hours?", "No. Our rates are the same 24/7. No weekend or holiday premiums."),
        ],
        "sdesc": "Professional electrical services including wiring repair, panel upgrades, lighting installation, outlet repair, and EV charger installation.",
        "ldesc": "power outages, faulty wiring, panel failures, electrical shorts, and surge damage",
    },
    "roofing": {
        "name": "Roofing",
        "icon": "128726",
        "tag": "ROOFING SERVICE",
        "cat": "roofing",
        "pricing": [
            ("Roof repair", "$350-$1,200", "$250-$800", "40-75 min"),
            ("Roof replacement", "$5,000-$15,000", "$3,500-$12,000", "2-5 days"),
            ("Leak repair", "$250-$800", "$150-$500", "30-60 min"),
            ("Gutter installation", "$400-$1,500", "$300-$1,200", "60-180 min"),
            ("Skylight installation", "$800-$2,500", "$600-$2,000", "90-180 min"),
            ("Roof inspection", "$150-$400", "$100-$300", "30-60 min"),
            ("Emergency tarping", "$500-$2,000", "N/A", "30-60 min"),
            ("Chimney flashing", "$300-$900", "$200-$700", "45-90 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} calls in {city} range from $150-$15,000 depending on the issue. Minor roof repairs run $250-$800 while full replacements can reach $15,000. We provide free estimates before starting work."),
            ("Do you offer 24/7 {service}?", "Yes. We provide 24/7 emergency {service} across {city} and all of Kent County — including nights, weekends, and holidays. Call {phone} for immediate dispatch."),
            ("Are your roofers licensed?", "All our roofers are licensed in Michigan (LARA), fully insured, and safety-trained. License verification available upon request."),
            ("How fast can you get to {city}?", "Average response times range from 25 minutes (downtown) to 75 minutes (outer suburbs). Emergency calls with active leaks get priority dispatch."),
            ("Do you warranty roofing work?", "Yes. All repairs carry a 1-year workmanship warranty. New roofs include manufacturer warranties plus our installation guarantee."),
            ("Can I prevent roofing emergencies?", "Regular inspections catch most issues early. We recommend bi-annual inspections, gutter cleaning, and trimming overhanging branches."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for nights or weekends?", "No. Our emergency rates are the same 24/7. Many roofers add premiums for after-hours calls — we don't."),
        ],
        "sdesc": "Professional roofing services including roof repair, replacement, leak detection, gutter installation, and emergency tarping.",
        "ldesc": "leaking roofs, storm damage, missing shingles, gutter failures, and skylight leaks",
    },
    "landscaping": {
        "name": "Landscaping",
        "icon": "127795",
        "tag": "LANDSCAPING SERVICE",
        "cat": "landscaping",
        "pricing": [
            ("Lawn mowing", "$40-$80", "$30-$60", "15-30 min"),
            ("Garden design", "$200-$800", "$150-$600", "60-120 min"),
            ("Tree trimming", "$200-$600", "$150-$450", "30-60 min"),
            ("Hardscaping", "$1,000-$5,000", "$800-$4,000", "1-3 days"),
            ("Irrigation installation", "$500-$2,000", "$400-$1,500", "60-180 min"),
            ("Sod installation", "$400-$1,500", "$300-$1,200", "2-4 hours"),
            ("Mulch & rock", "$150-$500", "$100-$400", "30-60 min"),
            ("Landscape lighting", "$300-$1,000", "$200-$800", "60-90 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $40-$5,000 depending on scope. Basic lawn care runs $40-$80 while full hardscaping can reach $5,000. Free estimates provided."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency {service} across {city} and Kent County for urgent issues like fallen trees or drainage emergencies. Call {phone}."),
            ("Are your landscapers licensed?", "Yes. All team members are trained, insured, and certified in proper landscaping techniques."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs) for emergency calls."),
            ("Do you warranty landscaping work?", "Yes. Plants carry a 1-year guarantee. Hardscaping and irrigation carry a 2-year workmanship warranty."),
            ("Can I prevent landscaping issues?", "Regular maintenance prevents most problems. We recommend seasonal cleanups, irrigation winterization, and early pest treatment."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same whether you book Tuesday or Saturday."),
        ],
        "sdesc": "Professional landscaping services including lawn care, garden design, hardscaping, irrigation, and seasonal maintenance.",
        "ldesc": "overgrown yards, drainage problems, dead trees, irrigation failures, and hardscape damage",
    },
    "concrete": {
        "name": "Concrete",
        "icon": "129521",
        "tag": "CONCRETE SERVICE",
        "cat": "concrete",
        "pricing": [
            ("Driveway repair", "$400-$1,500", "$300-$1,000", "45-90 min"),
            ("Patio installation", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Sidewalk repair", "$300-$900", "$200-$700", "40-75 min"),
            ("Foundation repair", "$2,000-$7,000", "$1,500-$5,000", "1-3 days"),
            ("Concrete resurfacing", "$500-$2,000", "$400-$1,500", "60-120 min"),
            ("Stamped concrete", "$2,000-$5,000", "$1,500-$4,000", "1-2 days"),
            ("Retaining wall", "$1,000-$4,000", "$800-$3,000", "1-2 days"),
            ("Concrete steps", "$400-$1,200", "$300-$900", "45-90 min"),
        ],
        "faq": [
            ("How much does {service} work cost in {city}?", "Most {service} projects in {city} range from $300-$7,000 depending on scope. Driveway repairs run $400-$1,500 while foundation work can reach $7,000. Free estimates provided."),
            ("Do you offer emergency {service}?", "Yes. We respond to urgent {service} needs across {city} and Kent County. Call {phone} for immediate dispatch."),
            ("Are your concrete specialists licensed?", "Yes. All our concrete contractors are licensed in Michigan, insured, and experienced in residential and commercial work."),
            ("How fast can you get to {city}?", "Average response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty concrete work?", "Yes. All concrete work carries a 2-year workmanship warranty against cracking and settling."),
            ("Can I prevent concrete damage?", "Seal concrete every 2-3 years, address drainage issues early, and avoid de-icing salts that cause spalling."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same 7 days a week."),
        ],
        "sdesc": "Professional concrete services including driveway repair, patio installation, foundation work, and decorative concrete.",
        "ldesc": "cracked driveways, sinking patios, foundation settling, spalling concrete, and trip hazards",
    },
    "fencing": {
        "name": "Fencing",
        "icon": "9923",
        "tag": "FENCING SERVICE",
        "cat": "fencing",
        "pricing": [
            ("Wood fence install", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Vinyl fence install", "$2,000-$5,000", "$1,500-$4,000", "1-2 days"),
            ("Fence repair", "$200-$600", "$150-$450", "30-60 min"),
            ("Gate installation", "$300-$1,000", "$200-$800", "45-90 min"),
            ("Chain link fence", "$800-$2,500", "$600-$2,000", "4-8 hours"),
            ("Privacy fence", "$2,000-$5,000", "$1,500-$4,000", "1-2 days"),
            ("Fence staining", "$300-$800", "$200-$600", "2-4 hours"),
            ("Post replacement", "$150-$400", "$100-$300", "30-60 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $150-$5,000 depending on materials and length. Wood fences run $1,500-$4,000 while vinyl is $2,000-$5,000."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency fence repair across {city} and Kent County for storm damage and fallen sections. Call {phone}."),
            ("Are your fence installers licensed?", "Yes. All our fencing contractors are licensed, insured, and experienced with all fence types."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty fencing work?", "Yes. All installations carry a 1-year workmanship warranty. Material warranties vary by manufacturer."),
            ("Can I prevent fence damage?", "Regular staining or sealing, keeping vegetation clear, and addressing loose posts early prevents most issues."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day of the week."),
        ],
        "sdesc": "Professional fencing services including wood, vinyl, and chain-link fence installation, repair, and replacement.",
        "ldesc": "fallen fences, rotten posts, broken gates, storm-damaged sections, and privacy screening",
    },
    "flooring": {
        "name": "Flooring",
        "icon": "128681",
        "tag": "FLOORING SERVICE",
        "cat": "flooring",
        "pricing": [
            ("Hardwood installation", "$3,000-$8,000", "$2,500-$7,000", "1-3 days"),
            ("Laminate flooring", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Tile installation", "$2,000-$5,000", "$1,500-$4,000", "1-2 days"),
            ("Carpet installation", "$1,000-$3,500", "$800-$3,000", "4-8 hours"),
            ("Vinyl flooring", "$1,200-$3,500", "$1,000-$3,000", "1-2 days"),
            ("Floor repair", "$200-$700", "$150-$500", "30-60 min"),
            ("Subfloor replacement", "$500-$2,000", "$400-$1,500", "60-120 min"),
            ("Floor refinishing", "$2,000-$5,000", "$1,500-$4,000", "1-3 days"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $200-$8,000 depending on material and room size. Hardwood runs $3,000-$8,000 while laminate is $1,500-$4,000."),
            ("Do you offer emergency {service}?", "Yes. We respond to urgent flooring needs across {city} and Kent County — including water-damaged flooring. Call {phone}."),
            ("Are your floor installers licensed?", "Yes. All our flooring specialists are licensed, insured, and trained in proper installation techniques."),
            ("How fast can you get to {city}?", "Response times for estimates and emergency work range from 25 minutes to 75 minutes across Kent County."),
            ("Do you warranty flooring work?", "Yes. All installations carry a 1-year workmanship warranty. Manufacturer warranties apply to materials."),
            ("Can I prevent flooring damage?", "Use felt pads on furniture, clean spills immediately, maintain proper humidity, and follow manufacturer care guidelines."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional flooring services including hardwood, laminate, tile, carpet, and vinyl installation, repair, and refinishing.",
        "ldesc": "worn carpets, damaged hardwood, cracked tiles, water-damaged floors, and subfloor issues",
    },
    "painting": {
        "name": "Painting",
        "icon": "127912",
        "tag": "PAINTING SERVICE",
        "cat": "painting",
        "pricing": [
            ("Interior painting", "$1,500-$4,000", "$1,200-$3,500", "1-3 days"),
            ("Exterior painting", "$2,000-$6,000", "$1,500-$5,000", "2-4 days"),
            ("Cabinet painting", "$800-$2,500", "$600-$2,000", "1-2 days"),
            ("Drywall repair", "$200-$600", "$150-$450", "30-60 min"),
            ("Wallpaper removal", "$400-$1,200", "$300-$1,000", "2-4 hours"),
            ("Trim painting", "$300-$900", "$200-$700", "1-2 hours"),
            ("Ceiling painting", "$400-$1,000", "$300-$800", "2-4 hours"),
            ("Deck staining", "$500-$1,500", "$400-$1,200", "2-4 hours"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $200-$6,000 depending on square footage. Interior painting runs $1,500-$4,000 for a typical home."),
            ("Do you offer emergency {service}?", "We offer priority scheduling for urgent painting needs across {city} and Kent County. Call {phone} for rapid service."),
            ("Are your painters licensed?", "Yes. All our painters are licensed, insured, and experienced in both residential and commercial work."),
            ("How fast can you get to {city}?", "We start most projects within 2-3 days. Emergency touch-ups and repairs within 24 hours."),
            ("Do you warranty painting work?", "Yes. All painting carries a 2-year workmanship warranty against peeling, cracking, or fading."),
            ("Can I extend paint life?", "Use quality paint, clean walls regularly, control humidity, and address moisture issues before they cause peeling."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional painting services including interior and exterior painting, cabinet refinishing, drywall repair, and deck staining.",
        "ldesc": "peeling paint, faded exteriors, damaged drywall, outdated cabinets, and stained decks",
    },
    "pest-control": {
        "name": "Pest Control",
        "icon": "128026",
        "tag": "PEST CONTROL SERVICE",
        "cat": "pest-control",
        "pricing": [
            ("General pest control", "$100-$300", "$80-$250", "20-45 min"),
            ("Termite treatment", "$1,000-$4,000", "$800-$3,500", "2-4 hours"),
            ("Rodent control", "$200-$600", "$150-$450", "30-60 min"),
            ("Bed bug treatment", "$500-$2,000", "$400-$1,500", "1-3 hours"),
            ("Ant control", "$100-$300", "$80-$250", "20-40 min"),
            ("Mosquito control", "$150-$400", "$100-$300", "30-45 min"),
            ("Wasp removal", "$150-$400", "$100-$300", "20-40 min"),
            ("Roach treatment", "$200-$500", "$150-$400", "30-60 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} treatments in {city} range from $80-$4,000. General pest control runs $100-$300 while termite treatment can reach $4,000."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency pest control across {city} and Kent County for active infestations. Call {phone}."),
            ("Are your pest control techs licensed?", "Yes. All technicians are Michigan-licensed, insured, and trained in integrated pest management."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty pest control?", "Yes. Treatments carry a 30-day guarantee. Quarterly plans include re-service at no charge between visits."),
            ("How can I prevent pests?", "Seal entry points, eliminate standing water, store food properly, and maintain regular treatment schedules."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day of the week."),
        ],
        "sdesc": "Professional pest control services including general pest management, termite treatment, rodent control, and bed bug elimination.",
        "ldesc": "ants in kitchen, rodents in attic, termite damage, bed bug infestations, and wasp nests",
    },
    "siding": {
        "name": "Siding",
        "icon": "128682",
        "tag": "SIDING SERVICE",
        "cat": "siding",
        "pricing": [
            ("Vinyl siding install", "$4,000-$12,000", "$3,000-$10,000", "2-5 days"),
            ("Siding repair", "$300-$1,000", "$200-$800", "45-90 min"),
            ("Aluminum siding", "$5,000-$14,000", "$4,000-$12,000", "2-5 days"),
            ("Wood siding", "$6,000-$15,000", "$5,000-$13,000", "3-7 days"),
            ("Siding replacement", "$5,000-$14,000", "$4,000-$12,000", "2-5 days"),
            ("Trim installation", "$500-$2,000", "$400-$1,500", "1-2 days"),
            ("Fascia & soffit", "$600-$2,500", "$500-$2,000", "1-2 days"),
            ("Siding cleaning", "$300-$800", "$200-$600", "2-4 hours"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $300-$15,000. Full siding installation runs $4,000-$12,000 while repairs are $300-$1,000."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency siding repair across {city} and Kent County for storm damage. Call {phone}."),
            ("Are your siding installers licensed?", "Yes. All our siding contractors are licensed, insured, and factory-trained on major siding brands."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty siding work?", "Yes. All installations carry a 2-year workmanship warranty. Material warranties range from 20-50 years."),
            ("How can I maintain siding?", "Clean annually with gentle washing, inspect for damage after storms, and seal gaps promptly."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same 7 days a week."),
        ],
        "sdesc": "Professional siding services including vinyl, aluminum, and wood siding installation, repair, and replacement.",
        "ldesc": "cracked siding, storm damage, loose panels, rotting wood, and faded exterior",
    },
    "window-replacement": {
        "name": "Window Replacement",
        "icon": "127380",
        "tag": "WINDOW SERVICE",
        "cat": "window-replacement",
        "pricing": [
            ("Window installation", "$400-$1,200", "$300-$1,000", "45-90 min per window"),
            ("Window repair", "$150-$500", "$100-$400", "30-60 min"),
            ("Glass replacement", "$200-$600", "$150-$500", "30-60 min"),
            ("Bay window install", "$1,500-$4,000", "$1,200-$3,500", "2-4 hours"),
            ("Casement window", "$400-$1,000", "$300-$800", "45-90 min"),
            ("Double-hung window", "$500-$1,200", "$400-$1,000", "45-90 min"),
            ("Sliding window", "$400-$1,000", "$300-$800", "45-90 min"),
            ("Storm window", "$200-$600", "$150-$500", "30-60 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $150-$4,000 per window. Standard double-hung windows run $500-$1,200 installed."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency glass replacement across {city} and Kent County for broken windows. Call {phone}."),
            ("Are your window installers licensed?", "Yes. All installers are licensed, insured, and trained on major window brands."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty window work?", "Yes. Installation carries a 1-year workmanship warranty. Window warranties range from 10-30 years."),
            ("Can I improve window efficiency?", "Consider double-pane or triple-pane windows, proper caulking, and weatherstripping to reduce energy loss."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional window replacement and repair services including installation, glass replacement, and energy-efficient upgrades.",
        "ldesc": "drafty windows, broken glass, rotting frames, failed seals, and outdated single-pane windows",
    },
    "deck-and-patio": {
        "name": "Deck & Patio",
        "icon": "127724",
        "tag": "DECK & PATIO SERVICE",
        "cat": "deck-and-patio",
        "pricing": [
            ("Deck construction", "$3,000-$10,000", "$2,500-$8,000", "2-5 days"),
            ("Deck repair", "$300-$1,200", "$200-$900", "45-90 min"),
            ("Patio installation", "$2,000-$6,000", "$1,500-$5,000", "2-4 days"),
            ("Pergola building", "$1,500-$5,000", "$1,200-$4,000", "1-3 days"),
            ("Deck staining", "$500-$1,500", "$400-$1,200", "2-4 hours"),
            ("Patio paver repair", "$300-$1,000", "$200-$800", "45-90 min"),
            ("Deck sealing", "$400-$1,200", "$300-$1,000", "2-4 hours"),
            ("Railing installation", "$500-$2,000", "$400-$1,500", "1-2 days"),
        ],
        "faq": [
            ("How much does {service} work cost in {city}?", "Most {service} projects in {city} range from $300-$10,000. Deck construction runs $3,000-$10,000 while patio installation is $2,000-$6,000."),
            ("Do you offer emergency {service}?", "Yes. We handle urgent deck repairs across {city} and Kent County. Call {phone} for immediate service."),
            ("Are your deck builders licensed?", "Yes. All contractors are licensed in Michigan, insured, and experienced in residential construction."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty deck work?", "Yes. All construction carries a 2-year workmanship warranty. Material warranties apply."),
            ("How can I extend deck life?", "Seal annually, clean twice yearly, inspect for rot, and keep vegetation away from the structure."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional deck and patio services including construction, repair, staining, and pergola installation.",
        "ldesc": "rotting deck boards, unstable railings, cracked patio pavers, and weathered outdoor structures",
    },
    "kitchen-remodeling": {
        "name": "Kitchen Remodeling",
        "icon": "128703",
        "tag": "KITCHEN REMODELING",
        "cat": "kitchen-remodeling",
        "pricing": [
            ("Cabinet installation", "$3,000-$10,000", "$2,500-$8,000", "2-4 days"),
            ("Countertop replacement", "$1,500-$5,000", "$1,200-$4,000", "1-2 days"),
            ("Backsplash installation", "$500-$2,000", "$400-$1,500", "1-2 days"),
            ("Plumbing relocation", "$500-$2,000", "$400-$1,500", "1-2 days"),
            ("Electrical rewiring", "$400-$1,500", "$300-$1,200", "1-2 days"),
            ("Flooring", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Lighting installation", "$300-$1,000", "$200-$800", "30-60 min"),
            ("Full kitchen remodel", "$15,000-$40,000", "$10,000-$35,000", "2-6 weeks"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $300-$40,000. Full remodels run $15,000-$40,000 while cabinet refacing is $3,000-$10,000."),
            ("Do you offer emergency {service}?", "Yes. We handle urgent kitchen repairs across {city} and Kent County. Call {phone}."),
            ("Are your remodelers licensed?", "Yes. All contractors are licensed in Michigan, insured, and experienced in kitchen renovation."),
            ("How fast can you get to {city}?", "We provide free estimates within 24-48 hours. Emergency repairs within 1-2 hours."),
            ("Do you warranty remodeling work?", "Yes. All work carries a 1-year workmanship warranty. Manufacturer warranties apply to materials."),
            ("What adds the most value to a kitchen remodel?", "Cabinet refacing, quartz countertops, and energy-efficient appliances offer the best return on investment."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional kitchen remodeling services including cabinet installation, countertop replacement, backsplash, and full renovations.",
        "ldesc": "outdated kitchens, damaged cabinets, broken countertops, poor layout, and worn flooring",
    },
    "bathroom-remodeling": {
        "name": "Bathroom Remodeling",
        "icon": "128704",
        "tag": "BATHROOM REMODELING",
        "cat": "bathroom-remodeling",
        "pricing": [
            ("Shower installation", "$2,000-$6,000", "$1,500-$5,000", "2-4 days"),
            ("Tub replacement", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Vanity installation", "$500-$2,000", "$400-$1,500", "1-2 hours"),
            ("Tile work", "$1,000-$4,000", "$800-$3,500", "1-3 days"),
            ("Plumbing fixtures", "$300-$1,500", "$200-$1,200", "30-90 min"),
            ("Lighting & vent fan", "$200-$800", "$150-$600", "30-60 min"),
            ("Flooring", "$800-$3,000", "$600-$2,500", "1-2 days"),
            ("Full bathroom remodel", "$8,000-$20,000", "$6,000-$17,000", "1-3 weeks"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $200-$20,000. Full remodels run $8,000-$20,000 while shower installation is $2,000-$6,000."),
            ("Do you offer emergency {service}?", "Yes. We handle urgent bathroom repairs across {city} and Kent County. Call {phone}."),
            ("Are your remodelers licensed?", "Yes. All contractors are licensed in Michigan, insured, and experienced in bathroom renovation."),
            ("How fast can you get to {city}?", "Free estimates within 24-48 hours. Emergency plumbing repairs within 1 hour."),
            ("Do you warranty remodeling work?", "Yes. All work carries a 1-year workmanship warranty. Manufacturer warranties apply to materials."),
            ("What adds the most value?", "Walk-in showers, double vanities, and heated floors offer the best return in bathroom remodels."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional bathroom remodeling services including shower and tub installation, tile work, vanity replacement, and full renovations.",
        "ldesc": "outdated bathrooms, cracked tile, leaking showers, old fixtures, and poor ventilation",
    },
    "basement-remodel": {
        "name": "Basement Remodeling",
        "icon": "128739",
        "tag": "BASEMENT REMODELING",
        "cat": "basement-remodeling",
        "pricing": [
            ("Basement waterproofing", "$2,000-$7,000", "$1,500-$5,000", "1-3 days"),
            ("Drywall installation", "$1,000-$4,000", "$800-$3,500", "2-4 days"),
            ("Flooring", "$1,500-$4,000", "$1,200-$3,500", "1-2 days"),
            ("Electrical wiring", "$500-$2,000", "$400-$1,500", "1-2 days"),
            ("Plumbing rough-in", "$1,000-$4,000", "$800-$3,000", "1-3 days"),
            ("Insulation", "$500-$2,000", "$400-$1,500", "1-2 days"),
            ("Ceiling installation", "$500-$1,500", "$400-$1,200", "1-2 days"),
            ("Full basement finish", "$15,000-$35,000", "$10,000-$30,000", "3-6 weeks"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} projects in {city} range from $500-$35,000. Full basement finishes run $15,000-$35,000 while waterproofing is $2,000-$7,000."),
            ("Do you offer emergency {service}?", "Yes. We handle urgent basement issues across {city} and Kent County. Call {phone}."),
            ("Are your contractors licensed?", "Yes. All contractors are licensed in Michigan, insured, and experienced in basement finishing."),
            ("How fast can you get to {city}?", "Free estimates within 24-48 hours. Emergency waterproofing within 1-2 hours."),
            ("Do you warranty basement work?", "Yes. All work carries a 1-year workmanship warranty. Waterproofing carries a 10-year transferable warranty."),
            ("Is basement finishing a good investment?", "Finished basements typically return 70-75% of cost at resale and add valuable living space."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional basement remodeling services including waterproofing, finishing, drywall, flooring, and full renovations.",
        "ldesc": "wet basements, cracks in foundation, unfinished space, mold growth, and outdated basements",
    },
    "garage-door": {
        "name": "Garage Door",
        "icon": "128295",
        "tag": "GARAGE DOOR SERVICE",
        "cat": "garage-door-services",
        "pricing": [
            ("Opener repair", "$150-$400", "$100-$300", "20-45 min"),
            ("Spring replacement", "$200-$400", "$150-$350", "20-40 min"),
            ("Door installation", "$800-$2,500", "$600-$2,000", "2-4 hours"),
            ("Cable repair", "$150-$350", "$100-$250", "20-40 min"),
            ("Track alignment", "$150-$400", "$100-$300", "20-45 min"),
            ("Panel replacement", "$300-$800", "$200-$600", "30-60 min"),
            ("Remote programming", "$50-$150", "$40-$100", "10-20 min"),
            ("Weather seal", "$100-$250", "$80-$200", "20-40 min"),
        ],
        "faq": [
            ("How much does {service} repair cost in {city}?", "Most {service} repairs in {city} range from $50-$2,500. Spring replacement runs $200-$400 while full door installation is $800-$2,500."),
            ("Do you offer 24/7 {service}?", "Yes. We provide 24/7 emergency {service} across {city} and Kent County. Call {phone} for immediate dispatch."),
            ("Are your technicians licensed?", "Yes. All technicians are licensed, insured, and trained on all major garage door brands."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty garage door work?", "Yes. All repairs carry a 1-year parts and labor warranty. New doors include manufacturer warranties."),
            ("How can I prevent garage door issues?", "Lubricate moving parts quarterly, test auto-reverse monthly, and inspect cables and springs annually."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for after-hours?", "No. Our rates are the same 24/7."),
        ],
        "sdesc": "Professional garage door services including opener repair, spring replacement, door installation, and emergency service.",
        "ldesc": "broken springs, faulty openers, off-track doors, broken cables, and damaged panels",
    },
    "tree-service": {
        "name": "Tree Service",
        "icon": "127794",
        "tag": "TREE SERVICE",
        "cat": "tree-service",
        "pricing": [
            ("Tree removal", "$500-$3,000", "$400-$2,500", "1-4 hours"),
            ("Stump grinding", "$150-$500", "$100-$400", "30-60 min"),
            ("Tree trimming", "$200-$800", "$150-$600", "30-90 min"),
            ("Emergency tree service", "$500-$3,500", "N/A", "30-60 min"),
            ("Lot clearing", "$1,000-$5,000", "$800-$4,000", "1-3 days"),
            ("Pruning", "$150-$500", "$100-$400", "20-45 min"),
            ("Cabling & bracing", "$200-$600", "$150-$500", "30-60 min"),
            ("Tree health assessment", "$100-$300", "$75-$250", "20-40 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} work in {city} ranges from $100-$5,000. Tree removal runs $500-$3,000 while stump grinding is $150-$500."),
            ("Do you offer emergency {service}?", "Yes. We provide 24/7 emergency tree service across {city} and Kent County for fallen trees and storm damage. Call {phone}."),
            ("Are your arborists certified?", "Yes. Our team includes ISA-certified arborists. All crew members are trained and insured."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty tree work?", "Yes. All work carries a 1-year guarantee. Tree health assessments include care recommendations."),
            ("When is the best time to trim trees?", "Late winter or early spring is ideal for most trees. Dead or hazardous branches should be removed immediately."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional tree services including removal, stump grinding, trimming, pruning, and emergency storm response.",
        "ldesc": "fallen trees, storm damage, overgrown branches, hazardous limbs, and dead trees",
    },
    "mold-remediation": {
        "name": "Mold Remediation",
        "icon": "128683",
        "tag": "MOLD REMEDIATION",
        "cat": "mold-remediation",
        "pricing": [
            ("Mold inspection", "$200-$500", "$150-$400", "30-60 min"),
            ("Mold removal", "$500-$3,000", "$400-$2,500", "1-3 hours"),
            ("Attic mold treatment", "$800-$2,500", "$600-$2,000", "2-4 hours"),
            ("Basement mold removal", "$1,000-$4,000", "$800-$3,500", "2-5 hours"),
            ("HVAC mold cleaning", "$500-$2,000", "$400-$1,500", "1-3 hours"),
            ("Crawlspace remediation", "$800-$3,000", "$600-$2,500", "2-4 hours"),
            ("Air quality testing", "$300-$600", "$250-$500", "30-60 min"),
            ("Mold prevention treatment", "$300-$1,000", "$250-$800", "1-2 hours"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} in {city} ranges from $200-$4,000. Basic mold removal runs $500-$3,000 while basement remediation is $1,000-$4,000."),
            ("Do you offer emergency {service}?", "Yes. We provide emergency mold remediation across {city} and Kent County. Call {phone} for immediate response."),
            ("Are your mold specialists certified?", "Yes. All specialists are IICRC-certified and follow EPA mold remediation guidelines."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty mold work?", "Yes. All remediation carries a 1-year guarantee against mold return when the moisture source is resolved."),
            ("How can I prevent mold?", "Control humidity below 60%, fix leaks immediately, ensure proper ventilation, and use dehumidifiers in basements."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for weekends?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional mold remediation services including inspection, removal, air quality testing, and prevention treatment.",
        "ldesc": "visible mold growth, musty odors, water damage mold, attic and basement mold, and health concerns",
    },
    "water-damage-restoration": {
        "name": "Water Damage Restoration",
        "icon": "128167",
        "tag": "WATER DAMAGE RESTORATION",
        "cat": "water-damage-restoration",
        "pricing": [
            ("Water extraction", "$400-$1,500", "$300-$1,200", "30-60 min"),
            ("Structural drying", "$500-$3,000", "$400-$2,500", "1-3 days"),
            ("Dehumidification", "$300-$1,000", "$250-$800", "1-3 days"),
            ("Sewage cleanup", "$1,000-$5,000", "$800-$4,000", "2-4 hours"),
            ("Flood damage repair", "$2,000-$8,000", "$1,500-$7,000", "2-5 days"),
            ("Ceiling repair", "$300-$1,500", "$200-$1,200", "1-2 hours"),
            ("Carpet drying", "$200-$600", "$150-$500", "1-3 hours"),
            ("Sanitization", "$300-$800", "$250-$700", "1-2 hours"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} in {city} ranges from $200-$8,000. Water extraction runs $400-$1,500 while full flood repair can reach $8,000."),
            ("Do you offer 24/7 {service}?", "Yes. We provide 24/7 emergency water damage restoration across {city} and Kent County. Call {phone}."),
            ("Are your restoration techs certified?", "Yes. All technicians are IICRC-certified in water damage restoration and mold remediation."),
            ("How fast can you get to {city}?", "Emergency response times range from 25 minutes (downtown) to 75 minutes (outer suburbs)."),
            ("Do you warranty restoration work?", "Yes. All work carries a 1-year workmanship warranty. Drying guarantees included in every job."),
            ("What should I do while waiting?", "Turn off water at the main valve, move valuables to dry areas, document damage with photos, and call your insurance."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you work with insurance?", "Yes. We work directly with all major insurance providers and can help document claims."),
        ],
        "sdesc": "Professional water damage restoration services including extraction, drying, sewage cleanup, flood repair, and sanitization.",
        "ldesc": "burst pipes, flooding, sewage backups, leaking roofs, and storm water damage",
    },
    "appliance-repair": {
        "name": "Appliance Repair",
        "icon": "128684",
        "tag": "APPLIANCE REPAIR",
        "cat": "appliance-repair",
        "pricing": [
            ("Refrigerator repair", "$150-$500", "$100-$400", "30-60 min"),
            ("Oven & stove repair", "$150-$450", "$100-$350", "30-50 min"),
            ("Dishwasher repair", "$150-$400", "$100-$300", "30-50 min"),
            ("Washer repair", "$150-$450", "$100-$350", "30-50 min"),
            ("Dryer repair", "$150-$450", "$100-$350", "30-50 min"),
            ("Microwave repair", "$100-$300", "$80-$250", "20-40 min"),
            ("Freezer repair", "$150-$450", "$100-$350", "30-50 min"),
            ("Appliance installation", "$100-$300", "$80-$250", "20-40 min"),
        ],
        "faq": [
            ("How much does {service} cost in {city}?", "Most {service} calls in {city} range from $80-$500. Refrigerator repair runs $150-$500 while microwave repair is $100-$300."),
            ("Do you offer 24/7 {service}?", "Yes. We provide emergency appliance repair across {city} and Kent County for critical appliances like refrigerators. Call {phone}."),
            ("Are your technicians certified?", "Yes. All technicians are factory-trained and certified on major appliance brands including GE, Whirlpool, Samsung, and LG."),
            ("How fast can you get to {city}?", "Response times range from 25 minutes (downtown) to 75 minutes (outer suburbs) for emergency calls."),
            ("Do you warranty appliance repairs?", "Yes. All repairs carry a 90-day parts and labor warranty. Extended warranties available."),
            ("How can I extend appliance life?", "Clean condenser coils, replace water filters annually, avoid overloading, and schedule annual maintenance."),
            ("What areas do you serve?", "We cover all of Kent County including {city}, Kentwood, Wyoming, East Grand Rapids, Walker, Ada, Cascade, Rockford, Jenison, and Hudsonville."),
            ("Do you charge extra for after-hours?", "No. Our rates are the same every day."),
        ],
        "sdesc": "Professional appliance repair services for refrigerators, ovens, dishwashers, washers, dryers, and more.",
        "ldesc": "broken refrigerators, malfunctioning ovens, leaking dishwashers, faulty washers, and non-drying dryers",
    },
}

# ─── CITY PROFILES ──────────────────────────────────────────────────
CITIES = {
    "grand-rapids": {"name": "Grand Rapids", "zip": "49503, 49504, 49505, 49506, 49507, 49508, 49525", "response": "25-50", "neighborhoods": "Ottawa Hills, Highland Park, John Ball Park, Roosevelt Park, West Grand, Alger Heights, Garfield Park, Boston Square, Eastown, Heritage Hill, Midtown, Creston"},
    "kentwood": {"name": "Kentwood", "zip": "49508, 49512, 49548", "response": "30-50", "neighborhoods": "Kentwood proper, South Kentwood, East Kentwood, Paris Township area"},
    "wyoming": {"name": "Wyoming", "zip": "49509, 49519, 49548", "response": "30-55", "neighborhoods": "Godfrey-Lee, Wyoming Park, Rogers Plaza area, 44th Street corridor"},
    "east-grand-rapids": {"name": "East Grand Rapids", "zip": "49506", "response": "25-45", "neighborhoods": "Gaslight Village, Wealthy Street corridor, Fisk Lake, Reeds Lake area"},
    "walker": {"name": "Walker", "zip": "49544, 49534", "response": "35-60", "neighborhoods": "Standale, Walker proper, Alpine Avenue corridor"},
    "ada": {"name": "Ada", "zip": "49301", "response": "40-65", "neighborhoods": "Ada Village, Cascade Township area, Fulton Street corridor"},
    "cascade": {"name": "Cascade", "zip": "49546, 49301", "response": "35-60", "neighborhoods": "Cascade Township, Thornapple River area, Cascade Village"},
    "rockford": {"name": "Rockford", "zip": "49341, 49351", "response": "45-75", "neighborhoods": "Rockford proper, Squire Park, Riverside Gardens, Rogue River area"},
    "jenison": {"name": "Jenison", "zip": "49428", "response": "40-65", "neighborhoods": "Jenison proper, Georgetown Township, Baldwin Street corridor"},
    "hudsonville": {"name": "Hudsonville", "zip": "49426", "response": "45-70", "neighborhoods": "Hudsonville proper, Georgetown Township, 32nd Avenue area"},
}

# ─── DIRECTORY PROFILES ─────────────────────────────────────────────
DIRS = {
    "emergency": {"title": "Emergency", "prefix": "emergency", "urgency": "emergency", "urgency_adj": "emergency dispatch, urgent response, immediate help"},
    "24_hour": {"title": "24-Hour", "prefix": "24-hour", "urgency": "24-hour", "urgency_adj": "24-hour availability, round-the-clock service, any time"},
    "same_day": {"title": "Same-Day", "prefix": "same-day", "urgency": "same-day", "urgency_adj": "same-day service, quick turnaround, rapid response"},
    "affordable": {"title": "Affordable", "prefix": "affordable", "urgency": "budget-friendly", "urgency_adj": "competitive pricing, budget-friendly options, value service"},
    "near_me": {"title": "Near Me", "prefix": "near-me", "urgency": "local", "urgency_adj": "local service, nearby technicians, close to home"},
    "neighborhoods": {"title": "Neighborhood", "prefix": "", "urgency": "neighborhood", "urgency_adj": "neighborhood service, local expertise, community-focused"},
}

PHONE = "(616) 555-0147"
EMAIL = "hello@grandrapidshomeservices.com"
AUTHOR = "Mike Vanderholt"
LICENSE = "MP-45728"
AUTHOR_BIO = "Licensed professional with 19+ years serving Kent County. Personally supervised over 4,200 service calls."


def slug_to_city(slug):
    """Convert 'grand-rapids' -> City profile"""
    return CITIES.get(slug, CITIES["grand-rapids"])


def detect_service(filename):
    """Detect service type from filename"""
    name = filename.lower().replace(".html", "")
    # Special alias: shower-remodel → bathroom-remodeling
    if "shower" in name:
        return "bathroom-remodeling"
    for sk, sv in SERVICES.items():
        if sk in name or sv["name"].lower().replace(" ", "-") in name:
            return sk
    # Fallback: try matching after the prefix
    for sk in SERVICES:
        if sk in name:
            return sk
    return "plumbing"


def detect_city(filename, dirname=""):
    """Detect city from filename"""
    name = filename.lower().replace(".html", "")
    # Check longer city names first to avoid "grand-rapids" matching "east-grand-rapids"
    for ck in sorted(CITIES.keys(), key=len, reverse=True):
        if ck in name:
            return ck
    # Try parent directory name for neighborhoods
    if "ada" in name:
        return "ada"
    if "cascade" in name:
        return "cascade"
    if "rockford" in name:
        return "rockford"
    if "walker" in name:
        return "walker"
    if "wyoming" in name:
        return "wyoming"
    return "grand-rapids"


def generate_image(service_key, city_key, filepath):
    """Generate WebP image for article"""
    sv = SERVICES[service_key]
    ci = CITIES[city_key]
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1200, 630
        img = Image.new("RGB", (W, H), "#0a0a0a")
        draw = ImageDraw.Draw(img)
        # Dark gradient
        for y in range(H):
            r1, g1, b1 = 15, 15, 15
            r2, g2, b2 = 26, 26, 46
            r = int(r1 + (r2 - r1) * y / H)
            g = int(g1 + (g2 - g1) * y / H)
            b = int(b1 + (b2 - b1) * y / H)
            for x in range(W):
                draw.point((x, y), fill=(r, g, b))
        # Diagonal lines texture
        for i in range(0, W + H, 40):
            for j in range(-10, 10):
                xx = i - int(y * 0.3) + j
                if 0 <= xx < W and 0 <= y < H:
                    px = img.getpixel((xx, y))
                    draw.point((xx, y), fill=(min(255, px[0] + 4), min(255, px[1] + 4), min(255, px[2] + 8)))
        # Top accent line
        for x in range(W):
            for y2 in range(0, 4):
                draw.point((x, y2), fill=(59, 90, 246))
        # Bottom line
        for x in range(W):
            for y2 in range(H - 3, H):
                px = img.getpixel((x, y2))
                draw.point((x, y2), fill=(min(255, px[0] + 15), min(255, px[1] + 15), min(255, px[2] + 20)))
        font_t = ImageFont.truetype("arialbd.ttf", 54)
        font_s = ImageFont.truetype("arial.ttf", 26)
        font_sm = ImageFont.truetype("arial.ttf", 16)
        font_b = ImageFont.truetype("arialbd.ttf", 13)
        # Badge
        badge = sv["tag"]
        bb = draw.textbbox((0, 0), badge, font=font_b)
        bw, bh = bb[2] - bb[0] + 36, bb[3] - bb[1] + 14
        draw.rounded_rectangle((60, 120, 60 + bw, 120 + bh), radius=18, fill="#3b5af6")
        draw.text((78, 127), badge, fill="#ffffff", font=font_b)
        # Title
        lines = [sv["name"], f"in {ci['name']}, MI"]
        ty = 190
        for line in lines:
            bb = draw.textbbox((0, 0), line, font=font_t)
            tw = bb[2] - bb[0]
            draw.text(((W - tw) // 2, ty), line, fill="#ffffff", font=font_t)
            ty += 68
        # Subtitle
        sub = f"Professional {ci['name']} {sv['name']} Services"
        bb = draw.textbbox((0, 0), sub, font=font_s)
        tw = bb[2] - bb[0]
        draw.text(((W - tw) // 2, ty + 15), sub, fill="#94a3b8", font=font_s)
        # Stats
        stats = [("4,200+", "Calls"), ("19+ Yrs", "Experience"), ("10 Cities", "Covered")]
        sy = ty + 90
        total_w = 0
        cw_list = []
        for val, label in stats:
            vb = draw.textbbox((0, 0), val, font=font_t)
            lb = draw.textbbox((0, 0), label, font=font_sm)
            cw = max(vb[2] - vb[0], lb[2] - lb[0]) + 50
            cw_list.append(cw)
            total_w += cw
        total_w += (len(stats) - 1) * 50
        sx = (W - total_w) // 2
        for i, (val, label) in enumerate(stats):
            x = sx + sum(cw_list[:i]) + i * 50
            vb = draw.textbbox((0, 0), val, font=font_t)
            vw = vb[2] - vb[0]
            draw.text((x + (cw_list[i] - vw) // 2, sy), val, fill="#3b5af6", font=font_t)
            lb = draw.textbbox((0, 0), label, font=font_sm)
            lw = lb[2] - lb[0]
            draw.text((x + (cw_list[i] - lw) // 2, sy + 56), label, fill="#64748b", font=font_sm)
        img.save(filepath, "WEBP", quality=95)
        return True
    except Exception as e:
        print(f"  Image error: {e}")
        return False


def generate_article(service_key, city_key, dir_key, out_path):
    """Generate a complete professional HTML article"""
    sv = SERVICES[service_key]
    ci = CITIES[city_key]
    dr = DIRS[dir_key]
    title = f"{sv['name']} in {ci['name']}, MI — Professional Service Guide"
    slug_city = city_key
    serv_slug = service_key.replace(" ", "-")
    hub_slug = sv["cat"]
    dir_prefix = dr["prefix"]
    if dir_prefix:
        img_path = f"/assets/images/{dir_prefix}-{serv_slug}-{slug_city}.webp"
        canonical = f"/{dir_prefix}-{serv_slug}-{slug_city}-mi/"
    else:
        img_path = f"/assets/images/{serv_slug}-{slug_city}.webp"
        canonical = f"/{serv_slug}-{slug_city}-mi/"
    phone = PHONE

    # Build pricing table
    pricing_rows = ""
    for i, (svc, emerg, std, resp) in enumerate(sv["pricing"]):
        bg = "#fff" if i % 2 == 0 else "#f8fafc"
        pricing_rows += f'<tr style="background:{bg};"><td style="padding:10px;border:1px solid #e2e8f0;">{svc}</td><td style="padding:10px;border:1px solid #e2e8f0;">{emerg}</td><td style="padding:10px;border:1px solid #e2e8f0;">{std}</td><td style="padding:10px;border:1px solid #e2e8f0;">{resp}</td></tr>\n'

    # Build FAQ
    faq_items = ""
    for q, a in sv["faq"]:
        q_text = q.format(service=sv["name"].lower(), city=ci["name"], phone=phone)
        a_text = a.format(service=sv["name"].lower(), city=ci["name"], phone=phone)
        faq_items += f'<div class="faq-item"><h3>{q_text}</h3><p>{a_text}</p></div>\n'

    # Build FAQ JSON-LD
    faq_json = []
    for q, a in sv["faq"][:8]:
        q_text = q.format(service=sv["name"].lower(), city=ci["name"], phone=phone)
        a_text = a.format(service=sv["name"].lower(), city=ci["name"], phone=phone)
        faq_json.append(f'{{"@type":"Question","name":{json.dumps(q_text)},"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(a_text)}}}}}')
    faq_ld = f'{{\"@context\":\"https://schema.org\",\"@type\":\"FAQPage\",\"mainEntity\":[{",".join(faq_json)}]}}'

    # Service areas table
    area_rows = ""
    city_items = list(CITIES.items())
    for i, (ck, cv) in enumerate(city_items):
        bg = "#fff" if i % 2 == 0 else "#f8fafc"
        area_rows += f'<tr style="background:{bg};"><td style="padding:10px;border:1px solid #e2e8f0;">{cv["name"]}</td><td style="padding:10px;border:1px solid #e2e8f0;">{cv["response"]} min</td><td style="padding:10px;border:1px solid #e2e8f0;">Full</td></tr>\n'

    # Additional costs table
    extra_costs = [
        ("Drywall repair", "$250-$930", "Access behind wall for repair"),
        ("Water damage restoration", "$1,200-$6,980", "Drying and mold prevention"),
        ("Flooring repair", "$500-$3,000", "Water-damaged flooring"),
        ("Mold remediation", "$1,320-$3,780", "Undetected leak cleanup"),
        ("Structural repair", "$800-$4,000", "Wall/ceiling reconstruction"),
    ]
    extra_rows = ""
    for i, (svc, cost, scenario) in enumerate(extra_costs):
        bg = "#fff" if i % 2 == 0 else "#f8fafc"
        extra_rows += f'<tr style="background:{bg};"><td style="padding:10px;border:1px solid #e2e8f0;">{svc}</td><td style="padding:10px;border:1px solid #e2e8f0;">{cost}</td><td style="padding:10px;border:1px solid #e2e8f0;">{scenario}</td></tr>\n'

    # Savings table
    savings = [
        ("Call during standard hours", "40-60%", "Schedule Mon-Fri 8 AM-5 PM if safe"),
        ("Annual maintenance plan", "$300-$800/yr", "Catches issues before emergencies"),
        ("Address issues early", "50%+", "Small repairs cost half of emergency fixes"),
        ("Bundle with other repairs", "$50-$200", "Same visit fee covers multiple fixes"),
    ]
    save_rows = ""
    for i, (strat, save, how) in enumerate(savings):
        bg = "#fff" if i % 2 == 0 else "#f8fafc"
        save_rows += f'<tr style="background:{bg};"><td style="padding:10px;border:1px solid #e2e8f0;">{strat}</td><td style="padding:10px;border:1px solid #e2e8f0;">{save}</td><td style="padding:10px;border:1px solid #e2e8f0;">{how}</td></tr>\n'

    # Comparison table
    comp_rows = f"""
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">When to call</td><td style="padding:10px;border:1px solid #e2e8f0;">Active emergency, immediate risk</td><td style="padding:10px;border:1px solid #e2e8f0;">Routine issue, minor problem</td></tr>
    <tr style="background:#f8fafc;"><td style="padding:10px;border:1px solid #e2e8f0;">Availability</td><td style="padding:10px;border:1px solid #e2e8f0;">24/7/365 including holidays</td><td style="padding:10px;border:1px solid #e2e8f0;">Mon-Sat, 7 AM-8 PM</td></tr>
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">Response time</td><td style="padding:10px;border:1px solid #e2e8f0;">20-90 minutes</td><td style="padding:10px;border:1px solid #e2e8f0;">2-6 hours</td></tr>
    <tr style="background:#f8fafc;"><td style="padding:10px;border:1px solid #e2e8f0;">Premium</td><td style="padding:10px;border:1px solid #e2e8f0;">Minimal after-hours fee</td><td style="padding:10px;border:1px solid #e2e8f0;">Standard rates apply</td></tr>
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">Parts</td><td style="padding:10px;border:1px solid #e2e8f0;">Most common on truck</td><td style="padding:10px;border:1px solid #e2e8f0;">All parts available</td></tr>
    """

    # Process table
    process_rows = """
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">1. You call</td><td style="padding:10px;border:1px solid #e2e8f0;">Live dispatcher answers — no voicemail</td><td style="padding:10px;border:1px solid #e2e8f0;">Immediate</td></tr>
    <tr style="background:#f8fafc;"><td style="padding:10px;border:1px solid #e2e8f0;">2. We dispatch</td><td style="padding:10px;border:1px solid #e2e8f0;">Nearest tech receives job details</td><td style="padding:10px;border:1px solid #e2e8f0;">Within 5 min</td></tr>
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">3. En route</td><td style="padding:10px;border:1px solid #e2e8f0;">ETA text with tech name + photo</td><td style="padding:10px;border:1px solid #e2e8f0;">Within 10 min</td></tr>
    <tr style="background:#f8fafc;"><td style="padding:10px;border:1px solid #e2e8f0;">4. On-site</td><td style="padding:10px;border:1px solid #e2e8f0;">Assessment + upfront pricing + repair</td><td style="padding:10px;border:1px solid #e2e8f0;">20-90 min</td></tr>
    <tr style="background:#fff;"><td style="padding:10px;border:1px solid #e2e8f0;">5. Complete</td><td style="padding:10px;border:1px solid #e2e8f0;">Full fix + cleanup + inspection</td><td style="padding:10px;border:1px solid #e2e8f0;">30-120 min</td></tr>
    <tr style="background:#f8fafc;"><td style="padding:10px;border:1px solid #e2e8f0;">6. Follow-up</td><td style="padding:10px;border:1px solid #e2e8f0;">48-hour check-in call</td><td style="padding:10px;border:1px solid #e2e8f0;">Next business day</td></tr>
    """

    dir_name = dr["title"]
    urgency_adj = dr["urgency_adj"]

    article = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{sv['name']} in {ci['name']}, MI — Professional Service Guide</title>
<meta name="description" content="Professional {sv['name'].lower()} services in {ci['name']}, MI. Licensed, insured, and available 24/7. Call {phone} for prompt service across Kent County.">
<link rel="canonical" href="{canonical}">
<meta name="geo.region" content="US-MI">
<meta name="geo.placename" content="{ci['name']}">
<meta name="geo.position" content="42.9634;-85.6681">
<meta name="ICBM" content="42.9634, -85.6681">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"{sv['name']} in {ci['name']}, MI","description":"Professional {sv['name'].lower()} services serving {ci['name']} and all of Kent County.","author":{{"@type":"Person","name":"{AUTHOR}","description":"{AUTHOR_BIO}"}},"publisher":{{"@type":"Organization","name":"Grand Rapids Home Services","url":"/"}},"datePublished":"2026-06-06","dateModified":"2026-06-06","image":"{img_path}"}}</script>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"LocalBusiness","name":"Grand Rapids Home Services — {sv['name']}","description":"Professional {sv['name'].lower()} serving {ci['name']} and all of Kent County.","telephone":"{phone}","priceRange":"$$","address":{{"@type":"PostalAddress","addressLocality":"{ci['name']}","addressRegion":"MI","addressCountry":"US"}},"areaServed":[{{"@type":"City","name":"{ci['name']}"}},{{"@type":"City","name":"Kentwood"}},{{"@type":"City","name":"Wyoming"}},{{"@type":"City","name":"East Grand Rapids"}},{{"@type":"City","name":"Walker"}},{{"@type":"City","name":"Ada"}},{{"@type":"City","name":"Cascade"}},{{"@type":"City","name":"Rockford"}},{{"@type":"City","name":"Jenison"}},{{"@type":"City","name":"Hudsonville"}}],"serviceArea":{{"@type":"AdministrativeArea","name":"Kent County, MI"}}}}</script>
<script type="application/ld+json">{faq_ld}</script>
<link rel="stylesheet" href="/assets/style.css">
</head>
<body itemscope itemtype="https://schema.org/Article">

<nav class="navbar">
    <div class="navbar-inner">
        <a href="/" class="navbar-logo">
            <div class="navbar-logo-icon">GR</div>
            <span>Grand Rapids</span> Home Services
        </a>
        <ul class="nav-links">
            <li><a href="/">Home</a></li>
            <li><a href="/blog">Blog</a></li>
            <li><a href="/hubs/{hub_slug}-grand-rapids">Services</a></li>
            <li><a href="/authority/service-areas">Service Areas</a></li>
            <li><a href="/authority/about-us">About</a></li>
            <li><a href="/authority/reviews-grand-rapids">Reviews</a></li>
            <li><a href="/authority/contact" class="nav-cta">Call Now</a></li>
        </ul>
        <button class="hamburger" aria-label="Menu">
            <span></span><span></span><span></span>
        </button>
    </div>
</nav>

<section class="article-header">
    <div class="container">
        <h1 itemprop="headline">{title}</h1>
        <p itemprop="description">{sv['sdesc']} Serving {ci['name']} and all of Kent County with {dir_name.lower()} availability.</p>
        <div style="font-size:0.9rem;color:#94a3b8;margin-top:8px;">
            By <span itemprop="author">{AUTHOR}</span>, Licensed Professional &bull; Updated June 2026 &bull; 19+ years serving Kent County
        </div>
    </div>
</section>

<div style="padding:0;margin:-20px 0 0;">
    <div class="container">
        <figure style="margin:0 auto;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.15);max-width:800px;">
            <img src="{img_path}" alt="{sv['name']} in {ci['name']}, MI — Professional Service Guide" style="width:100%;height:auto;display:block;" loading="eager" itemprop="image">
            <figcaption style="padding:10px 16px;font-size:0.85rem;color:#64748b;background:#f8fafc;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 12px 12px;">
                Professional {sv['name'].lower()} services available 24/7 across {ci['name']} and all of Kent County, MI
            </figcaption>
        </figure>
    </div>
</div>

<section class="section">
    <div class="container">
        <div class="article-content">

            <meta itemprop="datePublished" content="2026-06-06">

            <!-- TOC -->
            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;margin-bottom:32px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#1e293b,#334155);padding:14px 20px;">
                    <span style="color:#fff;font-weight:700;font-size:1rem;">&#9776; Table of Contents</span>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:2px;padding:12px;background:#f1f5f9;">
                    <a href="#costs" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">1</span>Pricing &amp; Costs</a>
                    <a href="#comparison" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">2</span>Emergency vs Standard</a>
                    <a href="#urgent" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">3</span>When You Need {sv['name']}</a>
                    <a href="#service-areas" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">4</span>Service Areas</a>
                    <a href="#waiting" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">5</span>Emergency Checklist</a>
                    <a href="#process" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">6</span>Response Process</a>
                    <a href="#additional-costs" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">7</span>Additional Costs</a>
                    <a href="#save-money" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">8</span>Ways to Save</a>
                    <a href="#faq" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">9</span>FAQ</a>
                    <a href="#why-us" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#fff;border-radius:6px;color:#1e293b;text-decoration:none;font-size:0.9rem;font-weight:500;transition:all .15s;" onmouseover="this.style.background='#eef2ff';this.style.color='#2563eb'" onmouseout="this.style.background='#fff';this.style.color='#1e293b'"><span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;background:#2563eb;color:#fff;border-radius:6px;font-size:0.75rem;font-weight:700;flex-shrink:0;">10</span>Why Choose Us</a>
                </div>
            </div>

            <p style="font-size:1.15rem;line-height:1.8;">When you need reliable {sv['name'].lower()} in {ci['name']}, MI, you need a team that responds fast, charges fairly, and fixes the problem permanently. Whether you're dealing with {sv['ldesc']}, our licensed professionals are ready to help.</p>

            <p>If you're searching for {sv['name'].lower()} in {ci['name']}, you've found the right team. We offer <strong>{urgency_adj}</strong> across {ci['name']} and all of Kent County. Our technicians are licensed, insured, and equipped to handle any situation.</p>

            <div class="info-box" style="background:#f0f7ff;border-left:4px solid #2563eb;padding:20px;border-radius:6px;margin:30px 0;">
                <h3 style="margin:0 0 8px;">Need {sv['name']} in {ci['name']}?</h3>
                <p style="margin:0;font-size:1.1rem;">Call {phone} — Live dispatcher, no voicemail. Serving {ci['name']} and all of Kent County.</p>
            </div>

            <hr>

            <!-- Pricing -->
            <h2 id="costs">{sv['name']} Pricing Table — {ci['name']}, MI</h2>
            <p>Below are estimated cost ranges for common {sv['name'].lower()} services in {ci['name']}. We provide upfront pricing before any work begins.</p>

            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Service</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Emergency Rate</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Standard Rate</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Response</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pricing_rows}
                    </tbody>
                </table>
            </div>

            <p style="font-size:0.9rem;color:#64748b;margin-top:8px;">Rates based on internal service data across 4,200+ calls. Emergency rates include after-hours dispatch priority. Standard rates apply Mon-Fri 8 AM-5 PM.</p>

            <hr>

            <!-- Comparison -->
            <h2 id="comparison">{dir_name} vs Standard Service</h2>
            <p>Not every issue requires immediate dispatch. Here's how to decide what you need:</p>

            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Factor</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">{dir_name} Service</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Standard Service</th>
                        </tr>
                    </thead>
                    <tbody>
                        {comp_rows}
                    </tbody>
                </table>
            </div>

            <p>If you're unsure whether your situation qualifies as urgent, <strong>call us anyway</strong>. Our dispatcher will assess and advise at no charge. It's better to call and not need it than to wait.</p>

            <hr>

            <!-- When You Need -->
            <h2 id="urgent">When You Need {sv['name']} in {ci['name']}</h2>
            <p>{sv['name']} issues can arise at any time. Here are common scenarios that require professional attention:</p>
            <ul>
                <li><strong>Complete system failure</strong> — No heat, no power, no water flow requiring immediate restoration</li>
                <li><strong>Safety hazards</strong> — Gas odors, exposed wires, structural risks that threaten your home</li>
                <li><strong>Visible damage</strong> — Water leaks, smoke, sparking, or visible system deterioration</li>
                <li><strong>Unusual sounds or smells</strong> — Banging, hissing, burning odors indicating system stress</li>
                <li><strong>Age-related failure</strong> — Systems over 15-20 years old that suddenly stop functioning</li>
            </ul>
            <p>For any of these situations in {ci['name']}, call {phone} immediately. We dispatch the nearest available technician.</p>

            <hr>

            <!-- Service Areas -->
            <h2 id="service-areas">Service Areas — {ci['name']} and Beyond</h2>
            <p>We provide {sv['name'].lower()} services across all of Kent County. Here are our average response times by city:</p>

            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">City</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Response Time</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Coverage</th>
                        </tr>
                    </thead>
                    <tbody>
                        {area_rows}
                    </tbody>
                </table>
            </div>

            <p>ZIP codes served in {ci['name']}: {ci['zip']}. Neighborhoods include {ci['neighborhoods']}.</p>

            <hr>

            <!-- Checklist -->
            <h2 id="waiting">What to Do While Waiting for Your Technician</h2>
            <ol style="font-size:1.05rem;line-height:2;">
                <li><strong>Ensure safety first</strong> — If you smell gas or see active hazards, evacuate and call 911</li>
                <li><strong>Shut off the system</strong> — Turn off the affected system at the main breaker or shutoff valve</li>
                <li><strong>Contain damage</strong> — Move valuables away, place towels or buckets if water is involved</li>
                <li><strong>Document everything</strong> — Take photos of damage for insurance purposes</li>
                <li><strong>Call us</strong> — {phone} — We'll guide you through additional steps specific to your situation</li>
            </ol>

            <p>Always prioritize safety. If you're unsure what to do, wait outside and let our professionals handle it.</p>

            <hr>

            <!-- Process -->
            <h2 id="process">Our Response Process</h2>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Step</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Action</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Timeframe</th>
                        </tr>
                    </thead>
                    <tbody>
                        {process_rows}
                    </tbody>
                </table>
            </div>

            <hr>

            <!-- Additional Costs -->
            <h2 id="additional-costs">Additional Repair Costs to Consider</h2>
            <p>After the primary repair is complete, you may need additional restoration work:</p>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Service</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Cost Range</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Typical Scenario</th>
                        </tr>
                    </thead>
                    <tbody>
                        {extra_rows}
                    </tbody>
                </table>
            </div>

            <hr>

            <!-- Ways to Save -->
            <h2 id="save-money">Ways to Save on {sv['name']} Services</h2>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#1e293b;color:#fff;">
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Strategy</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">Savings</th>
                            <th style="padding:12px;text-align:left;border:1px solid #334155;">How It Works</th>
                        </tr>
                    </thead>
                    <tbody>
                        {save_rows}
                    </tbody>
                </table>
            </div>

            <p>We also offer <a href="/authority/financing">financing options</a> for larger repairs. Our goal is to fix the problem permanently — not to maximize the bill.</p>

            <hr>

            <!-- FAQ -->
            <h2 id="faq">Frequently Asked Questions</h2>
            {faq_items}

            <hr>

            <!-- Why Us -->
            <h2 id="why-us">Why {ci['name']} Homeowners Choose Us</h2>
            <p>Most {sv['name'].lower()} companies in {ci['name']} fall into two camps: national franchises with high overhead or small independents who can't staff 24/7. We bridge that gap.</p>
            <ul>
                <li><strong>Licensed professionals on every call</strong> — Not helpers, not apprentices. Experienced, licensed technicians.</li>
                <li><strong>1-year warranty</strong> — Industry standard is 30-90 days. We triple it.</li>
                <li><strong>Upfront pricing</strong> — You approve the price before we start work.</li>
                <li><strong>{dir_name} availability</strong> — If it can't wait, we're there. If it can, we fit you in quickly.</li>
                <li><strong>Live dispatch 24/7</strong> — No voicemail, no call center. Real people answering your call.</li>
            </ul>

            <div class="info-box" style="background:#f0f7ff;border-left:4px solid #2563eb;padding:20px;border-radius:6px;margin:30px 0;">
                <h3 style="margin:0 0 8px;">24/7 Service Dispatch</h3>
                <p style="margin:0;font-size:1.15rem;">Call <strong>{phone}</strong> — Response time: {ci['response']} minutes. Serving {ci['name']} and all of Kent County.</p>
            </div>

            <p style="font-size:0.9rem;color:#64748b;border-top:1px solid #e2e8f0;padding-top:16px;margin-top:30px;">
                <em>Article by <strong>{AUTHOR}</strong>, Licensed Professional (License #{LICENSE}). 19+ years serving Kent County with over 4,200 service calls. Last updated: June 2026.</em>
            </p>

            <h3>Related Resources</h3>
            <ul>
                <li><a href="/hubs/{hub_slug}-grand-rapids">{sv['name']} Services Guide →</a></li>
                <li><a href="/authority/service-areas">Service Areas →</a></li>
                <li><a href="/blog">Home Service Blog →</a></li>
            </ul>

            <h3>External References</h3>
            <ol style="font-size:0.9rem;">
                <li><a href="https://www.michigan.gov/lara" rel="nofollow noopener" target="_blank">Michigan LARA — License Verification</a></li>
                <li><a href="https://www.epa.gov/watersense" rel="nofollow noopener" target="_blank">EPA WaterSense Program</a></li>
                <li><a href="https://www.angi.com" rel="nofollow noopener" target="_blank">Angi — Service Cost Guide</a></li>
                <li><a href="https://www.grandrapidsmi.gov" rel="nofollow noopener" target="_blank">City of Grand Rapids</a></li>
            </ol>

        </div>
    </div>
</section>

<footer class="footer">
    <div class="container">
        <div class="footer-grid">
            <div>
                <a href="/" class="footer-brand">Grand Rapids Home Services</a>
                <p style="line-height:1.6;">1234 Plainfield Ave NE<br>Grand Rapids, MI 49505</p>
                <p style="margin-top:12px;">Phone: <a href="tel:{phone}">{phone}</a></p>
                <p>Email: {EMAIL}</p>
            </div>
            <div>
                <h4>Services</h4>
                <a href="/hubs/plumbing-grand-rapids">Plumbing</a>
                <a href="/hubs/hvac-grand-rapids">HVAC</a>
                <a href="/hubs/electrical-grand-rapids">Electrical</a>
                <a href="/hubs/roofing-grand-rapids">Roofing</a>
                <a href="/hubs/appliance-repair-grand-rapids">Appliance Repair</a>
                <a href="/hubs/painting-grand-rapids">Painting</a>
            </div>
            <div>
                <h4>Company</h4>
                <a href="/authority/about-us">About Us</a>
                <a href="/authority/contact">Contact</a>
                <a href="/authority/service-areas">Service Areas</a>
                <a href="/authority/reviews-grand-rapids">Reviews</a>
                <a href="/authority/financing">Financing</a>
                <a href="/authority/warranties">Warranties</a>
            </div>
            <div>
                <h4>Support</h4>
                <a href="/blog">Blog</a>
                <a href="/authority/emergency-service">Emergency Service</a>
                <a href="/authority/contact">Get a Quote</a>
                <a href="/sitemap/sitemap-index.xml">Sitemap</a>
                <a href="/authority/about-us">Privacy Policy</a>
            </div>
        </div>
        <div class="footer-bottom">
            &copy; 2015&ndash;2026 Grand Rapids Home Services. All rights reserved.
        </div>
    </div>
</footer>

<button class="back-to-top" aria-label="Back to top">&#8593;</button>
<script src="/assets/script.js"></script>
</body>
</html>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(article)
    return True


def process_all():
    """Process all articles across all directories"""
    IMAGES.mkdir(parents=True, exist_ok=True)

    dirs_map = {
        "emergency": "emergency",
        "24_hour": "24_hour",
        "same_day": "same_day",
        "affordable": "affordable",
        "near_me": "near_me",
        "neighborhoods": "neighborhoods",
    }

    total = 0
    errors = 0
    skipped = 0

    for dir_key, dir_path in dirs_map.items():
        full_path = ROOT / dir_path
        if not full_path.exists():
            print(f"  [SKIP] {dir_path} not found")
            continue

        files = list(full_path.glob("*.html"))
        print(f"\n{'='*50}")
        print(f"{dir_key.upper()} — {len(files)} files")
        print(f"{'='*50}")

        for fpath in files:
            try:
                service_key = detect_service(fpath.name)
                city_key = detect_city(fpath.name, dir_key)
                sv = SERVICES.get(service_key)
                ci = CITIES.get(city_key)

                if not sv or not ci:
                    skipped += 1
                    continue

                # Generate image
                dr = DIRS[dir_key]
                img_name = f"{dir_key}-{service_key}-{city_key}.webp" if dr["prefix"] else f"{service_key}-{city_key}.webp"
                img_path = IMAGES / img_name
                if not img_path.exists():
                    generate_image(service_key, city_key, img_path)

                # Generate article
                generate_article(service_key, city_key, dir_key, fpath)
                total += 1

                if total % 50 == 0:
                    print(f"  ✓ {total} articles generated...")

            except Exception as e:
                errors += 1
                print(f"  ✗ {fpath.name}: {e}")

    print(f"\n{'='*50}")
    print(f"DONE: {total} articles generated, {errors} errors, {skipped} skipped")
    print(f"{'='*50}")


if __name__ == "__main__":
    process_all()
