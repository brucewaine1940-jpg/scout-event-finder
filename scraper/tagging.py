"""Keyword tagging: merit badges, trainings, topics and program levels.

Everything here is plain keyword matching so it runs free inside GitHub Actions.
Edit the lists below to improve tagging - no other code needs to change.
"""
import re

# ---------------------------------------------------------------------------
# Merit badges. Key = official name; value = extra spellings to match.
# ---------------------------------------------------------------------------
MERIT_BADGES = {
    "American Business": [], "American Cultures": [], "American Heritage": [],
    "American Labor": [], "Animal Science": [], "Animation": [], "Archaeology": [],
    "Archery": [], "Architecture": [], "Art": [], "Astronomy": [], "Athletics": [],
    "Automotive Maintenance": ["auto maintenance"], "Aviation": [],
    "Backpacking": [], "Basketry": [], "Bird Study": [], "Bugling": [],
    "Camping": [], "Canoeing": [], "Chemistry": [], "Chess": [],
    "Citizenship in the Community": ["cit in the community", "citizenship in community", "cit comm"],
    "Citizenship in the Nation": ["cit in the nation", "citizenship in nation", "cit nation"],
    "Citizenship in Society": ["cit in society"],
    "Citizenship in the World": ["cit in the world", "citizenship in world", "cit world"],
    "Climbing": [], "Coin Collecting": [], "Collections": [], "Communication": [],
    "Composite Materials": [], "Cooking": [], "Crime Prevention": [], "Cycling": [],
    "Dentistry": [], "Digital Technology": [], "Disabilities Awareness": ["disability awareness"],
    "Dog Care": [], "Drafting": [], "Electricity": [], "Electronics": [],
    "Emergency Preparedness": ["emergency prep"], "Energy": [], "Engineering": [],
    "Entrepreneurship": [], "Environmental Science": ["env science", "enviro science"],
    "Exploration": [], "Family Life": [], "Farm Mechanics": [], "Fingerprinting": [],
    "Fire Safety": [], "First Aid": [],
    "Fish and Wildlife Management": ["fish & wildlife", "fish and wildlife"],
    "Fishing": [], "Fly Fishing": [], "Forestry": [], "Game Design": [],
    "Gardening": [], "Genealogy": [], "Geocaching": [], "Geology": [], "Golf": [],
    "Graphic Arts": [], "Health Care Professions": ["healthcare professions", "medicine"],
    "Hiking": [], "Home Repairs": [], "Horsemanship": [], "Insect Study": [],
    "Inventing": [], "Journalism": [], "Kayaking": [], "Landscape Architecture": [],
    "Law": [], "Leatherwork": [], "Lifesaving": [], "Mammal Study": [],
    "Metalwork": [], "Mining in Society": [], "Model Design and Building": ["model design"],
    "Motorboating": [], "Moviemaking": [], "Multisport": [], "Music": [], "Nature": [],
    "Nuclear Science": [], "Oceanography": [], "Orienteering": [], "Painting": [],
    "Personal Fitness": [], "Personal Management": ["personal mgmt"], "Pets": [],
    "Photography": [], "Pioneering": [], "Plant Science": [], "Plumbing": [],
    "Pottery": [], "Programming": [], "Public Health": [], "Public Speaking": [],
    "Pulp and Paper": [], "Radio": [], "Railroading": [], "Reading": [],
    "Reptile and Amphibian Study": ["reptile & amphibian", "reptile and amphibian"],
    "Rifle Shooting": [], "Robotics": [], "Rowing": [], "Safety": [],
    "Salesmanship": [], "Scholarship": [], "Scouting Heritage": [], "Scuba Diving": [],
    "Sculpture": [], "Search and Rescue": ["search & rescue"], "Shotgun Shooting": [],
    "Signs, Signals, and Codes": ["signs signals and codes", "signs, signals and codes"],
    "Skating": [], "Small-Boat Sailing": ["small boat sailing"], "Snow Sports": [],
    "Soil and Water Conservation": ["soil & water conservation"],
    "Space Exploration": [], "Sports": [], "Stamp Collecting": [], "Surveying": [],
    "Sustainability": [], "Swimming": [], "Textile": [], "Theater": [],
    "Traffic Safety": [], "Truck Transportation": [], "Veterinary Medicine": [],
    "Water Sports": [], "Weather": [], "Welding": [], "Whitewater": [],
    "Wilderness Survival": [], "Wood Carving": ["woodcarving"], "Woodwork": ["woodworking"],
}

# A badge name only counts when the event is clearly about merit badges
# (otherwise "Camping" or "Safety" would tag every campout and training).
BADGE_CONTEXT = re.compile(
    r"merit[\s-]*badge|\bMBs?\b|\bMBU\b|\bMBC\b|badge (?:day|university|college|clinic|weekend|workshop|fair|midway|class)|"
    r"midway", re.I)

# ---------------------------------------------------------------------------
# Adult & youth trainings / certifications
# ---------------------------------------------------------------------------
TRAININGS = {
    "Wood Badge": [r"wood\s*badge"],
    "NYLT": [r"\bNYLT\b", r"national youth leadership"],
    "NAYLE": [r"\bNAYLE\b"],
    "IOLS": [r"\bIOLS\b", r"introduction to outdoor leader"],
    "BALOO": [r"\bBALOO\b"],
    "Wilderness First Aid": [r"wilderness first aid", r"\bWFA\b", r"\bWFR\b", r"wilderness first responder"],
    "CPR / AED / First Aid": [r"\bCPR\b", r"\bAED\b", r"first aid (?:course|class|training|certification)"],
    "Hazardous Weather": [r"hazardous weather"],
    "Range Officer / Shooting Instructor": [r"range (?:safety )?officer", r"\bRSO\b", r"range ?master",
                                            r"\bNRA\b.*instructor", r"shooting sports director", r"\bNFAA\b", r"\bUSA ?Archery\b",
                                            r"angling instructor"],
    "Leave No Trace": [r"leave no trace", r"\bLNT\b"],
    "Aquatics (Lifeguard / Water Rescue)": [r"\blifeguard", r"aquatics? (?:supervision|instructor|director)",
                                            r"swimming (?:and|&) water rescue", r"paddle ?craft safety", r"safe swim"],
    "Climbing Instructor": [r"climb(?:ing)? (?:on )?safely", r"climbing (?:instructor|director)"],
    "Chainsaw / Tools": [r"chain ?saw"],
    "Kodiak": [r"\bkodiak\b"],
    "Powder Horn": [r"powder ?horn"],
    "Cold Weather (OKPIK)": [r"\bokpik\b", r"cold weather (?:camping|training)"],
    "Commissioner / University of Scouting": [r"commissioner (?:college|training|conference)", r"university of scouting"],
    "Position-Specific Leader Training": [r"position[- ]specific", r"scoutmaster (?:specific|training)",
                                          r"cub (?:leader|master) training", r"den leader training", r"leader training"],
    "Safeguarding Youth / YPT": [r"safeguarding youth", r"youth protection"],
    "Merit Badge Counselor": [r"merit badge counsel"],
    "Philmont Leadership Challenge": [r"philmont leadership challenge"],
}

# ---------------------------------------------------------------------------
# Topics / event types (broad buckets for browsing)
# ---------------------------------------------------------------------------
TOPICS = {
    "Merit Badge Program": [r"merit[\s-]*badge", r"\bMBU\b", r"badge (?:day|university|college|midway|fair|clinic)"],
    "Rank Advancement (TFC / Eagle)": [r"trail to first class", r"\bTFC\b", r"first year (?:camper|program)",
                                       r"path to eagle", r"eagle (?:workshop|seminar|clinic|coach|board|project)", r"\bBrownsea\b"],
    "Summer Camp / Resident Camp": [r"summer camp", r"resident camp", r"long[- ]term camp"],
    "Day Camp": [r"day camp", r"twilight camp"],
    "Camporee / Campout": [r"camporee", r"campout", r"camp[- ]out", r"cuboree", r"jamboree", r"family camp", r"overnight"],
    "High Adventure": [r"high adventure", r"philmont", r"sea base", r"northern tier", r"summit bechtel", r"\bsummit\b"],
    "Shooting Sports": [r"shoot", r"rifle", r"shotgun", r"archery", r"\bBB\b", r"sling ?shot", r"\brange\b", r"sporting clays", r"muzzle"],
    "Aquatics & Boating": [r"swim", r"kayak", r"canoe", r"paddl", r"boat", r"sail", r"snorkel", r"scuba", r"aquatic", r"rowing"],
    "Climbing": [r"climb", r"rappel", r"\bCOPE\b", r"zip ?line"],
    "Hiking & Backpacking": [r"\bhike", r"hiking", r"backpack", r"trek\b"],
    "Winter Sports": [r"\bski\b", r"skiing", r"snowboard", r"\bsnow\b", r"klondike", r"okpik", r"sled"],
    "STEM": [r"\bSTEM\b", r"robot", r"science", r"engineer", r"coding", r"nova award", r"astronom", r"space"],
    "Service": [r"service project", r"day of service", r"cleanup", r"clean[- ]up", r"food drive", r"scouting for food"],
    "Pinewood Derby / Races": [r"derby", r"regatta", r"space race"],
    "Order of the Arrow": [r"order of the arrow", r"\bOA\b", r"\blodge\b", r"ordeal", r"conclave", r"fellowship"],
    "Fundraising / Dinners": [r"fundrais", r"popcorn", r"dinner", r"luncheon", r"golf (?:classic|outing|tournament)",
                              r"sporting clays", r"gala", r"breakfast", r"\bdues\b", r"donat", r"challenge coin", r"auction"],
    "Meetings & Admin": [r"committee meeting", r"commissioners?(?:'s)? (?:monthly )?meeting", r"board(?:s)? of review", r"\bBOR\b",
                         r"roundtable", r"chapter meeting", r"monthly meeting", r"staff meeting", r"executive board",
                         r"key ?3", r"\bLEC\b", r"lodge executive", r"planning meeting", r"district meeting",
                         r"annual (?:business )?meeting", r"\bdues\b", r"recharter", r"membership (?:chair|meeting)"],
    "Fun / Family Events": [r"halloween", r"haunted", r"trunk or treat", r"family", r"festival", r"fun day", r"carnival", r"movie night"],
}

PROGRAM_KEYWORDS = {
    "Cub Scouts": [r"\bcubs?\b", r"\blions?\b", r"\btigers?\b", r"\bwolf\b", r"\bbears?\b", r"webelos", r"arrow of light",
                   r"\bAOL\b", r"\bpack\b", r"\bden\b", r"cuboree", r"\bBALOO\b"],
    "Scouts BSA": [r"scouts bsa", r"trail to first class", r"\bTFC\b", r"path to eagle", r"\btroops?\b", r"merit[\s-]*badge", r"\bpatrol", r"\bNYLT\b", r"\beagle\b"],
    "Venturing": [r"ventur"],
    "Sea Scouts": [r"sea scout"],
    "Exploring": [r"\bexplor(?:ing|er post)"],
    "Adults / Leaders": [r"\btraining\b", r"\bleaders?\b", r"\badults?\b", r"alumni", r"commissioner", r"roundtable",
                         r"wood\s*badge", r"\bdinner\b", r"volunteer"],
}

# Site category ids -> labels (from the filter on global.scoutingevent.com)
SITE_CATEGORIES = {
    12: "Advancement", 13: "Alumni / Adult", 7: "Commissioners", 26: "DEI Events",
    15: "Fundraising", 16: "Membership", 17: "National Camps & Events", 14: "OA",
    5: "Program or Camp Event", 8: "Special Needs and Disabilities", 18: "Territory Wide Events",
    6: "Training & Leadership", 20: "Cub Scout", 19: "Exploring", 21: "Scouts BSA",
    22: "Sea Scout", 23: "STEM", 25: "Venturing",
}
SITE_CATEGORY_TO_PROGRAM = {20: "Cub Scouts", 21: "Scouts BSA", 25: "Venturing", 22: "Sea Scouts",
                            19: "Exploring", 13: "Adults / Leaders", 7: "Adults / Leaders"}


def _compile(d):
    return {k: re.compile("|".join(v), re.I) for k, v in d.items()}


_TRAIN = _compile(TRAININGS)
_TOPIC = _compile(TOPICS)
_PROG = _compile(PROGRAM_KEYWORDS)
_BADGE = {}
for name, alts in MERIT_BADGES.items():
    forms = [name] + alts
    if "," in name:
        forms.append(name.replace(",", ""))
    pat = "|".join(r"\b" + re.escape(f).replace(r"\ ", r"[\s-]+") + r"\b" for f in forms)
    _BADGE[name] = re.compile(pat, re.I)

# Phrases that contain a badge word but are NOT that badge.
_NOT_BADGE = re.compile(
    r"wilderness first aid|first aid (?:course|class|certification|training|kit)|swimming (?:and|&) water rescue|"
    r"climb(?:ing)? on safely|climbing (?:tower|wall|instructor|director)|cold[- ]weather(?: camping)?|winter camping|hazardous weather|"
    r"weather permitting|inclement weather|shooting sports|safety afloat|range safety|safety officer|"
    r"youth (?:protection|safety)|safe swim|camping (?:trip|weekend|season)|family camping|"
    r"campership|scholarships? (?:available|fund|application)|eagle scholarship|sports? (?:complex|field|center)", re.I)
# Longest names first so "Fire Safety" is consumed before "Safety", "Fly Fishing" before "Fishing".
_BADGE_ORDER = sorted(_BADGE, key=len, reverse=True)
_MB_NEAR = re.compile(r"merit[\s-]*badges?|\bMBs?\b", re.I)


def _find_badges(text, near_only):
    """Badge names in text. near_only: the name must sit within ~60 chars of 'merit badge'/'MB'."""
    scan = _NOT_BADGE.sub(lambda m: " " * len(m.group()), text)
    found = []
    for name in _BADGE_ORDER:
        for m in _BADGE[name].finditer(scan):
            if near_only and not _MB_NEAR.search(scan[max(0, m.start() - 60): m.end() + 60]):
                continue
            found.append(name)
            scan = _BADGE[name].sub(lambda mm: " " * len(mm.group()), scan)  # consume
            break
    return found


GENERIC = ("Art", "Safety", "Sports", "Reading", "Nature", "Energy", "Law", "Music", "Communication",
           "Pets", "Radio", "Collections", "Scholarship", "Exploration", "Camping", "Weather", "Hiking", "Cooking",
           "Swimming", "Climbing", "Fishing", "Painting", "Theater", "Golf", "Signs, Signals, and Codes")


def tag(title, desc, site_cats):
    """Return dict of tag lists for one event."""
    text = f"{title}\n{desc or ''}"
    badges = []
    title_is_badge_event = bool(BADGE_CONTEXT.search(title)) or 12 in site_cats
    if title_is_badge_event:
        # A merit badge program (MBU, badge day...): any badge named anywhere counts,
        # but very generic words must be in the title or Capitalized in the description.
        badges = _find_badges(text, near_only=False)
        badges = [b for b in badges if b not in GENERIC or _BADGE[b].search(title) or
                  re.search(r"\b" + re.escape(b).replace(r"\ ", r"[\s-]+") + r"\b", desc or "")]
    elif BADGE_CONTEXT.search(text):
        # Something else (summer camp, NYLT...) that mentions merit badges: only names right next to "merit badge".
        badges = _find_badges(text, near_only=True)
        badges = [b for b in badges if b not in GENERIC or _BADGE[b].search(title) or
                  re.search(r"\b" + re.escape(b).replace(r"\ ", r"[\s-]+") + r"\b", desc or "")]
    trainings = [k for k, rx in _TRAIN.items() if rx.search(text)]
    topics = [k for k, rx in _TOPIC.items() if rx.search(text)]
    if badges and "Merit Badge Program" not in topics:
        topics.insert(0, "Merit Badge Program")
    if trainings:
        topics.append("Training")
    programs = {SITE_CATEGORY_TO_PROGRAM[c] for c in site_cats if c in SITE_CATEGORY_TO_PROGRAM}
    # Title is the strongest signal for audience; use description only if title says nothing.
    title_prog = {k for k, rx in _PROG.items() if rx.search(title)}
    programs |= title_prog or {k for k, rx in _PROG.items() if rx.search(text)}
    if badges:
        programs.add("Scouts BSA")
    return {
        "badges": sorted(badges),
        "trainings": sorted(trainings),
        "topics": topics,
        "programs": sorted(programs),
        "categories": sorted(SITE_CATEGORIES[c] for c in site_cats if c in SITE_CATEGORIES),
    }
