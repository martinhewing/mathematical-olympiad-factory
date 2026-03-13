"""
connectionsphere_factory/curriculum.py

Chapter 1 — Scale from Zero to Millions of Users
Source: System Design Interview (ByteByteGo, Alex Xu), Chapter 1, pp. 1–31

This module is the single source of truth for the TEACH phase and Jordan's
interview probes. Nothing here is generated at runtime — it is hard-coded from
the book and reviewed for accuracy.

Claude's role is ENRICHMENT ONLY:
  - Vary the analogy Alex uses to explain each concept
  - Personalise the comprehension check question wording
  - Generate the reference SVG diagram for each concept (cached globally)

Structure of each concept entry:
  id                  — stable key used for caching, routing, and rubric lookup
  name                — display name shown in the UI
  order               — teach sequence (1-indexed, matches book progression)
  core_facts          — verbatim distillation of the book's key points;
                        Alex MUST cover all of these; Claude cannot omit or alter them
  why_it_matters      — the "so what" Alex leads with; grounds the concept in reality
  book_pages          — page reference for traceability
  diagram_prompt      — instruction passed to Claude to generate the reference SVG;
                        precise enough that Claude produces a consistent, correct diagram
  diagram_type        — "reference" (shown during teach) | "evolution" (shows before/after)
  solicit_drawing     — True = Alex asks candidate to draw this; Jordan will also probe it
  drawing_rubric      — ordered list of elements the candidate diagram MUST contain;
                        used by Claude to score the candidate's uploaded drawing
  jordan_minimum_bar  — the lowest acceptable answer before Jordan flags the stage
  jordan_probes       — the exact follow-up questions Jordan uses, in escalation order
  common_mistakes     — what weak candidates say; used to calibrate Jordan's scoring
  faang_signal        — what a strong hire signal looks like on this concept
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DrawingRubricItem:
    label: str          # short name shown in UI feedback
    description: str    # what Claude checks for in the candidate's diagram
    required: bool      # True = must be present for PASS; False = nice-to-have


@dataclass
class Concept:
    id:                 str
    name:               str
    order:              int
    core_facts:         list[str]
    why_it_matters:     str
    book_pages:         str
    diagram_prompt:     str
    diagram_type:       str                      # "reference" | "evolution"
    solicit_drawing:    bool
    drawing_rubric:     list[DrawingRubricItem]
    jordan_minimum_bar: str
    jordan_probes:      list[str]
    common_mistakes:    list[str]
    faang_signal:       str
    alex_analogy_seed:  str   # hint to Claude for the real-world analogy to use


# ─────────────────────────────────────────────────────────────────────────────
# SVG style guide — injected into every diagram_prompt so Claude produces
# visually consistent diagrams across all concepts
# ─────────────────────────────────────────────────────────────────────────────

SVG_STYLE_GUIDE = """
SVG constraints (enforce strictly):
- viewBox="0 0 680 420", xmlns="http://www.w3.org/2000/svg"
- Background: rect fill="#0f1117" (dark, matches UI theme)
- Boxes: rect rx="6", fill="#1e2130", stroke="#3a3f55", stroke-width="1.5"
- Primary arrows: stroke="#6c8ebf", stroke-width="1.5", marker-end="url(#arrow)"
- Replication/secondary arrows: stroke="#5a9e6f" (green), stroke-width="1.2", stroke-dasharray="5,3"
- Labels inside boxes: font-family="'DM Mono', monospace", font-size="12", fill="#c9d1d9"
- Sublabels / IP addresses: font-size="10", fill="#8b949e"
- Section grouping labels (e.g. "Web Tier"): font-size="11", fill="#6e7681", font-style="italic"
- Dashed group boundaries: rect stroke="#3a3f55", stroke-dasharray="6,3", fill="none", rx="8"
- Define arrowhead marker: <marker id="arrow" markerWidth="8" markerHeight="8"
    refX="6" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#6c8ebf"/>
  </marker>
- No drop shadows. No gradients. No colour fills on boxes.
- All text horizontally centred within its box unless it is a flow label on an arrow.
- Minimum padding inside boxes: 10px on all sides.
- Do NOT include DOCTYPE, xml declaration, or <html> tags.
- Return raw SVG only — nothing else.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Concept 1 — Single Server Setup
# ─────────────────────────────────────────────────────────────────────────────

_C1 = Concept(
    id    = "single_server",
    name  = "Single Server Setup",
    order = 1,
    book_pages = "pp. 1–3",

    core_facts = [
        "Everything runs on one box: web app, database, cache.",
        "Request flow: user → DNS (paid 3rd-party service) → IP address → HTTP request → web server → HTML or JSON response.",
        "Two traffic sources: web application (server-side language + client-side HTML/JS) and mobile application (HTTP + JSON API).",
        "JSON is the dominant API response format between mobile clients and servers.",
        "DNS is NOT hosted on your servers — it is a third-party paid service.",
    ],

    why_it_matters = (
        "Every production system started here. Understanding this baseline lets you "
        "articulate *why* each subsequent layer exists — which is exactly what Jordan "
        "is listening for."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram for a single-server web setup.

{SVG_STYLE_GUIDE}

Elements to include (top to bottom, left to right):

1. Top-left group box labelled "User" containing:
   - A laptop icon (simple rectangle + small screen rectangle) labelled "Web browser"
   - A phone icon (thin rectangle) labelled "Mobile app"
   Both side-by-side inside the User box.

2. Top-right: a circle/globe shape labelled "DNS" with the text "3rd-party service" beneath it in sublabel style.

3. Arrow FROM User box TO DNS labelled "① api.mysite.com"
4. Arrow FROM DNS BACK TO User box labelled "② IP address (e.g. 15.125.23.214)"

5. Below the User box: a single dashed-border server box labelled "Web Server"
   Inside the Web Server box, three stacked sub-labels:
   - "Web App"
   - "Database"
   - "Cache"

6. Arrow FROM User box DOWN TO Web Server labelled "③ HTTP request"
7. Arrow FROM Web Server UP TO User box (dashed return) labelled "④ HTML / JSON"

Add a small footnote at bottom: "Figure 1-1 — Single server: everything on one box"
""",

    diagram_type    = "reference",
    solicit_drawing = False,   # Too simple — verbal explanation is sufficient

    drawing_rubric = [],  # Not solicited

    jordan_minimum_bar = (
        "Candidate must identify that web traffic and database traffic should be "
        "separated into distinct tiers, and explain why (independent scaling, "
        "fault isolation). Naming DNS as a third-party service is a nice signal."
    ),

    jordan_probes = [
        "Walk me through what happens when a user types mysite.com into their browser.",
        "What's the problem with keeping the database on the same server as your web app?",
        "Your mobile app and web app are both hitting this server. How does the server know which format to return?",
        "DNS — is that something you manage, or is it external? Why does that matter?",
    ],

    common_mistakes = [
        "Saying 'the server handles DNS' — DNS is always third-party.",
        "Not distinguishing between web app traffic (HTML) and mobile traffic (JSON).",
        "Jumping to scale solutions before articulating why the single-server model breaks.",
    ],

    faang_signal = (
        "Candidate proactively explains *why* the single-server model is the starting "
        "point (simplicity, low traffic), then immediately articulates the first failure "
        "mode (no isolation between tiers) without being prompted."
    ),

    alex_analogy_seed = (
        "A small restaurant where the chef also takes orders, manages the till, and "
        "cleans tables — fine when quiet, chaos when busy."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 2 — Database Tier Separation
# ─────────────────────────────────────────────────────────────────────────────

_C2 = Concept(
    id    = "database_separation",
    name  = "Database Tier Separation",
    order = 2,
    book_pages = "pp. 4–5",

    core_facts = [
        "Separating the web server and database onto different machines allows each tier to be scaled independently.",
        "Relational databases (RDBMS / SQL): MySQL, PostgreSQL, Oracle. Represent and store data in tables and rows. Support JOIN operations across tables.",
        "Non-relational databases (NoSQL): CouchDB, Neo4j, Cassandra, HBase, DynamoDB. Four categories: key-value stores, graph stores, column stores, document stores. JOIN operations generally NOT supported.",
        "Choose NoSQL when: super-low latency required; data is unstructured or non-relational; only need to serialise/deserialise (JSON, XML, YAML); storing a massive amount of data.",
        "For most use cases, relational databases are the right default — 40+ years of proven reliability.",
    ],

    why_it_matters = (
        "This is the first architectural decision Jordan will push on. The moment you "
        "say 'I'd use a database', you need to justify SQL vs NoSQL with trade-offs, "
        "not just name-drop a technology."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing web tier and database tier separation.

{SVG_STYLE_GUIDE}

Elements:

1. Top: User group box (same as single-server diagram — laptop + phone)
2. DNS globe top-right, arrows for DNS lookup and IP address return (same as C1)

3. Middle-left: dashed group box labelled "Web Tier"
   Inside: a single server box labelled "Web Server"

4. Middle-right: dashed group box labelled "Data Tier"
   Inside: a cylinder/database shape labelled "Database"

5. Arrows:
   - User → Web Server: "www.mysite.com"
   - User → Web Server: "api.mysite.com" (second arrow, slightly offset)
   - Web Server → Database: "read/write/update" (solid arrow right)
   - Database → Web Server: "return data" (dashed arrow left, green)

6. The two dashed group boxes should be clearly separate with visible gap between them.

Footnote: "Figure 1-3 — Web tier and data tier separated for independent scaling"
""",

    diagram_type    = "reference",
    solicit_drawing = False,

    drawing_rubric = [],

    jordan_minimum_bar = (
        "Candidate must name at least one concrete trade-off between SQL and NoSQL "
        "for the specific problem at hand, not a generic list. Must identify that "
        "tier separation enables independent scaling."
    ),

    jordan_probes = [
        "You've separated the database — SQL or NoSQL? Walk me through your reasoning for this problem specifically.",
        "What are the four categories of NoSQL database? Which would you reach for here and why?",
        "I'm looking at your design — both tiers are still single points of failure. What happens if the database goes down?",
        "Give me a scenario where you'd abandon your preferred database choice and switch.",
    ],

    common_mistakes = [
        "Picking NoSQL because it 'scales better' without explaining the specific trade-off.",
        "Not knowing the four NoSQL categories (key-value, graph, column, document).",
        "Forgetting that JOIN operations are generally unsupported in NoSQL.",
        "Failing to mention that tier separation enables independent scaling.",
    ],

    faang_signal = (
        "Candidate states a default (relational) and the specific conditions under "
        "which they'd deviate — with at least one concrete example from the problem "
        "domain. Mentions JOIN limitations proactively when NoSQL is chosen."
    ),

    alex_analogy_seed = (
        "Splitting the kitchen from the dining room — now you can hire more chefs "
        "without buying more tables, or add seating without expanding the kitchen."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 3 — Vertical vs Horizontal Scaling
# ─────────────────────────────────────────────────────────────────────────────

_C3 = Concept(
    id    = "scaling_models",
    name  = "Vertical vs Horizontal Scaling",
    order = 3,
    book_pages = "pp. 5–6",

    core_facts = [
        "Vertical scaling (scale up): add more power (CPU, RAM, etc.) to existing servers. Simple but has a hard limit — you cannot add unlimited resources to one machine.",
        "Horizontal scaling (scale out): add more servers to the pool. Preferred for large-scale applications.",
        "Vertical scaling has NO failover or redundancy — if the server goes down, the site goes down.",
        "Vertical scaling is appropriate when traffic is low and simplicity is valued. It is not a long-term solution.",
        "Horizontal scaling requires a load balancer to distribute traffic across servers.",
    ],

    why_it_matters = (
        "'How would you scale this?' is the most common Jordan follow-up in the "
        "entire interview. You need the vocabulary, the trade-offs, and the ability "
        "to say *why* horizontal is preferred at scale — not just that it is."
    ),

    diagram_prompt = f"""
Generate an SVG diagram comparing vertical and horizontal scaling side-by-side.

{SVG_STYLE_GUIDE}

Layout: two panels side by side, separated by a vertical dividing line and "VS" label in the centre.

LEFT PANEL — "Vertical Scaling (Scale Up)":
- One large server box, taller than a normal server box
- An upward arrow on the left side of the box labelled "Add CPU / RAM / DISK"
- Below box: label "Hard limit reached"
- Below that: label "Single point of failure"
- Small ✗ icon (red cross) in corner

RIGHT PANEL — "Horizontal Scaling (Scale Out)":
- Three server boxes of equal normal size arranged in a 3x1 row
- A right-pointing arrow between them suggesting "add more →"
- Below: label "No hard limit"
- Below that: label "Redundancy built in"
- Small ✓ icon (green check) in corner

Centre divider: vertical line with "VS" label in the middle

Footnote: "Figure 1-20 — Vertical scaling hits a ceiling; horizontal scaling grows indefinitely"
""",

    diagram_type    = "reference",
    solicit_drawing = False,

    drawing_rubric = [],

    jordan_minimum_bar = (
        "Candidate must name the two models with correct terminology (scale up / scale out), "
        "explain at least two limitations of vertical scaling, and state that horizontal "
        "scaling requires a load balancer."
    ),

    jordan_probes = [
        "You said you'd scale horizontally — what does that require that your current design doesn't have?",
        "Stack Overflow ran 10 million monthly users on a single master database in 2013. Does that change how you think about vertical scaling?",
        "What are the two hard limits of vertical scaling?",
        "If I give you unlimited budget for one beefy server vs ten smaller ones — which do you pick and why?",
    ],

    common_mistakes = [
        "Saying 'just add more servers' without mentioning the need for a load balancer.",
        "Not knowing that vertical scaling has no failover — if the big server dies, everything dies.",
        "Treating horizontal scaling as purely about performance rather than also about availability.",
    ],

    faang_signal = (
        "Candidate links the failover problem directly to the load balancer solution "
        "without being prompted. Understands that vertical scaling is not inherently "
        "wrong — it is appropriate at small scale — but has a hard ceiling."
    ),

    alex_analogy_seed = (
        "One very strong waiter vs hiring more waiters. There is a limit to how fast "
        "one person can run — but you can keep hiring."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 4 — Load Balancer
# ─────────────────────────────────────────────────────────────────────────────

_C4 = Concept(
    id    = "load_balancer",
    name  = "Load Balancer",
    order = 4,
    book_pages = "pp. 6–7",

    core_facts = [
        "A load balancer evenly distributes incoming traffic among web servers in a load-balanced set.",
        "Users connect to the load balancer's PUBLIC IP. Web servers are UNREACHABLE directly from the internet.",
        "Web servers communicate with each other and the load balancer via PRIVATE IPs (reachable only within the same network).",
        "Failover: if Server 1 goes offline, all traffic is rerouted to Server 2 automatically. A new healthy server is added to restore balance.",
        "Elasticity: if traffic spikes, just add more servers to the pool. The load balancer starts sending requests to them immediately.",
    ],

    why_it_matters = (
        "The load balancer is the single most common component Jordan asks candidates "
        "to draw. If you can't explain public vs private IP in this context, "
        "Jordan will probe until you can — or flag the stage."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing a load balancer setup.

{SVG_STYLE_GUIDE}

Elements (top to bottom):

1. Top: User group box (laptop + phone)
2. DNS globe top-right, DNS lookup / IP return arrows

3. Below User: Load Balancer box (slightly wider than server boxes)
   - Label: "Load Balancer"
   - Sub-label: "Public IP: 88.88.88.1"
   - Arrow FROM DNS table (small table below DNS showing domain→IP mapping) TO Load Balancer
   - Arrow FROM User TO Load Balancer labelled "Public IP: 88.88.88.1"

4. Below Load Balancer: dashed group box labelled "Web Tier"
   Inside: two server boxes side by side
   - Server 1: labelled "Server 1" with sub-label "Private IP: 10.0.0.1"
   - Server 2: labelled "Server 2" with sub-label "Private IP: 10.0.0.2"

5. Arrows FROM Load Balancer TO Server 1 and Server 2 (fork pattern, both solid)
   Label on arrows: "Private IP only"

6. Small legend box bottom-right:
   "Public IP → reachable from internet"
   "Private IP → internal network only"

Footnote: "Figure 1-4 — Load balancer with private IP isolation"
""",

    diagram_type    = "reference",
    solicit_drawing = True,   # Jordan always asks for this

    drawing_rubric = [
        DrawingRubricItem(
            label       = "Load balancer present",
            description = "A load balancer component is drawn between the user and the web servers.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Public IP on load balancer",
            description = "The load balancer is labelled with a public IP or indicated as publicly accessible.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "At least 2 web servers",
            description = "Two or more web server boxes are shown behind the load balancer.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Private IP isolation indicated",
            description = "The web servers are shown with private IPs or labelled as not directly internet-accessible.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Failover path implied",
            description = "The diagram implies that traffic reroutes if one server fails (e.g. arrows to both servers, redundancy label).",
            required    = False,
        ),
        DrawingRubricItem(
            label       = "DNS present",
            description = "DNS is shown resolving the domain to the load balancer's public IP.",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must correctly place the load balancer between the user and web servers, "
        "articulate the public/private IP split, and explain the failover and elasticity "
        "benefits. Drawing must include a load balancer and at least 2 servers."
    ),

    jordan_probes = [
        "Draw me the load balancer setup. I want to see where public and private IPs live.",
        "Your Server 1 just went offline at 3am. Walk me through exactly what happens.",
        "Traffic just tripled in five minutes. How does your load balancer handle that?",
        "Why can't I just give users the IP address of Server 1 directly?",
        "What is a sticky session? Why is it sometimes needed and what's the downside?",
    ],

    common_mistakes = [
        "Putting the load balancer AFTER the DNS rather than as the DNS target.",
        "Not knowing what a private IP is or why web servers need them.",
        "Thinking the load balancer solves the database bottleneck — it only addresses the web tier.",
        "Not mentioning sticky sessions when the interviewer hints at stateful web servers.",
    ],

    faang_signal = (
        "Candidate draws the diagram correctly on first attempt, proactively explains "
        "the private IP rationale for security, and mentions that the load balancer "
        "itself becomes a single point of failure — and how to address it."
    ),

    alex_analogy_seed = (
        "An airport check-in desk manager who directs passengers to whichever desk "
        "has the shortest queue. The passengers only interact with the manager, "
        "never directly with the desk agents."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 5 — Database Replication
# ─────────────────────────────────────────────────────────────────────────────

_C5 = Concept(
    id    = "database_replication",
    name  = "Database Replication (Master / Slave)",
    order = 5,
    book_pages = "pp. 7–10",

    core_facts = [
        "Master database: handles ALL write operations (insert, delete, update). Typically only one master.",
        "Slave databases: receive copies of data from master; handle READ operations only. Usually multiple slaves.",
        "Most applications have far more reads than writes → slave count is usually much larger than master count.",
        "Advantages: better read performance (queries distributed across slaves), reliability (data replicated across locations), high availability (if one DB goes offline, another serves traffic).",
        "If a slave goes offline: reads temporarily redirected to master or other slaves. New slave provisioned to replace it.",
        "If the master goes offline: a slave is promoted to master. Data recovery scripts may be needed if slave data is behind. Multi-master and circular replication exist but are more complex.",
    ],

    why_it_matters = (
        "Every system design problem at FAANG scale involves database availability. "
        "Jordan will always ask what happens when the database goes down. "
        "This is your answer."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing master-slave database replication.

{SVG_STYLE_GUIDE}

Elements:

1. Top: Web Servers group box (dashed) containing two small server icons side by side.
   Label: "Web Servers"

2. Left side, vertically below: Master DB cylinder
   Label: "Master DB"
   Sub-label: "Writes only"
   Arrow FROM Web Servers TO Master DB labelled "writes"

3. Right side: three Slave DB cylinders stacked vertically
   - "Slave DB1" — arrow FROM Master DB labelled "DB replication →"
   - "Slave DB2" — arrow FROM Master DB labelled "DB replication →"
   - "Slave DB3" — arrow FROM Master DB labelled "DB replication →"
   All replication arrows should be dashed green.

4. Arrows FROM Web Servers to each Slave DB labelled "reads"
   These arrows are solid blue.

5. Small callout box: "Reads >> Writes in most apps → more slaves than masters"

Footnote: "Figure 1-5 — Master-slave replication: writes to master, reads distributed to slaves"
""",

    diagram_type    = "reference",
    solicit_drawing = True,

    drawing_rubric = [
        DrawingRubricItem(
            label       = "Master DB labelled write-only",
            description = "The master database is present and indicated as handling writes.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "At least 2 slave DBs",
            description = "Two or more slave databases are drawn.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Replication arrows from master to slaves",
            description = "Arrows flow from master to slaves indicating data replication.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Read traffic goes to slaves",
            description = "Web servers are shown routing read queries to slaves, not master.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Write traffic goes to master only",
            description = "Write operations from web servers go only to the master DB.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Slave promotion on master failure indicated",
            description = "Some indication that a slave becomes master on failure (label, note, or arrow).",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must correctly distinguish master (writes) from slave (reads), "
        "explain the failover behaviour for both cases (slave offline, master offline), "
        "and articulate why slave count exceeds master count in real systems."
    ),

    jordan_probes = [
        "Draw the database replication model. Show me where reads and writes go.",
        "The master database just went offline. Walk me through exactly what happens next.",
        "You've got one slave. It goes down. Where do reads go?",
        "Why do systems typically have more slave databases than master databases?",
        "What are the risks of promoting a slave to master automatically?",
        "How does replication improve performance beyond just availability?",
    ],

    common_mistakes = [
        "Sending writes to slaves — slaves are READ ONLY.",
        "Not knowing what happens when the master goes offline (slave promotion).",
        "Forgetting that promoted slaves may have stale data requiring recovery scripts.",
        "Not explaining the read performance benefit (distributing queries across slaves).",
    ],

    faang_signal = (
        "Candidate explains the slave promotion complexity unprompted — specifically that "
        "in production, automated promotion is risky because slave data may lag, "
        "and mentions multi-master as an alternative with its own trade-offs."
    ),

    alex_analogy_seed = (
        "A publishing house with one editor-in-chief (master) who approves all changes, "
        "and multiple copy desks (slaves) who each keep an up-to-date copy for readers."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 6 — Cache Tier
# ─────────────────────────────────────────────────────────────────────────────

_C6 = Concept(
    id    = "cache_tier",
    name  = "Cache Tier",
    order = 6,
    book_pages = "pp. 11–13",

    core_facts = [
        "A cache is temporary storage that holds results of expensive queries or frequently accessed data in memory so subsequent requests are served without hitting the database.",
        "Cache tier sits between web server and database. Web server checks cache first; on miss, queries database and stores result in cache.",
        "Read-through cache: the most common pattern. If data is in cache → return it. If not → query DB → store in cache → return.",
        "Considerations: use cache for data read frequently but modified infrequently. Do NOT use cache as the only storage (volatile memory — lost on restart).",
        "Expiration policy: too short → frequent DB calls; too long → stale data. Balance is required.",
        "Consistency challenge: keeping data store and cache in sync is hard, especially across multiple regions.",
        "Single Point of Failure: a single cache server is a SPOF. Use multiple cache servers across data centres.",
        "Eviction policies: Least Recently Used (LRU) is most common. Also: LFU (Least Frequently Used), FIFO (First In First Out).",
    ],

    why_it_matters = (
        "Cache is the answer to 'how do you reduce database load?' in almost every "
        "system design question. Jordan expects you to know not just what a cache is, "
        "but the failure modes — stale data, SPOF, consistency across regions."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing the cache tier between web server and database.

{SVG_STYLE_GUIDE}

Elements (left to right flow):

1. Left: Web Server box
   Label: "Web Server"

2. Centre: Cache box (slightly rounded, distinct from server boxes)
   Label: "Cache"
   Sub-label: "(e.g. Redis / Memcached)"

3. Right: Database cylinder
   Label: "Database"

4. Arrows showing the read-through cache flow:
   a. Web Server → Cache: "① Check cache" (solid arrow right)
   b. Cache → Web Server: "1a. Cache HIT → return data" (dashed arrow left, green)
   c. Cache → Database: "1b. Cache MISS → query DB" (solid arrow right, continues past cache)
   d. Database → Cache: "② Store in cache" (dashed arrow left, green)
   e. Cache → Web Server: "③ Return data" (dashed arrow left, green, final return)

5. Small annotation box above or below the cache:
   "Data read frequently, modified rarely"
   "Volatile — lost on restart"
   "LRU eviction by default"

Footnote: "Figure 1-7 — Read-through cache: check cache first, fall through to DB on miss"
""",

    diagram_type    = "reference",
    solicit_drawing = True,

    drawing_rubric = [
        DrawingRubricItem(
            label       = "Cache positioned between web server and DB",
            description = "Cache layer is drawn between the web server and database, not as a sidecar or after DB.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Cache-first check shown",
            description = "Arrow from web server to cache (checking cache before going to DB) is present.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Cache miss path to DB shown",
            description = "Arrow from cache (or web server) to database on cache miss is present.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Cache population on miss shown",
            description = "Data flows from DB back through cache before returning to web server (cache-and-return).",
            required    = False,
        ),
        DrawingRubricItem(
            label       = "Cache technology named",
            description = "Redis or Memcached is named on the diagram.",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must describe read-through cache correctly, identify at least two "
        "of the four considerations (expiration, consistency, SPOF, eviction policy), "
        "and explain that cache is NOT a persistent storage layer."
    ),

    jordan_probes = [
        "Walk me through the read-through cache flow. What happens on a cache miss?",
        "A cache server restarts. What happens to all the data in it?",
        "How do you keep the cache consistent with the database when data changes?",
        "You have one cache server. What's the problem with that at scale?",
        "What's LRU? Give me a scenario where LFU would be a better choice.",
        "When should you NOT use a cache?",
    ],

    common_mistakes = [
        "Treating cache as permanent storage — it is volatile and will be lost on restart.",
        "Not knowing LRU eviction (the most common cache eviction policy).",
        "Not addressing the consistency problem between cache and database.",
        "Placing only one cache server without mentioning SPOF risk.",
    ],

    faang_signal = (
        "Candidate proactively addresses the consistency problem (cache invalidation "
        "is hard, especially across regions) and mentions that the Facebook Scaling "
        "Memcache paper is the canonical reference for this problem at scale."
    ),

    alex_analogy_seed = (
        "The frequently asked questions board in a busy office — instead of asking "
        "HR the same question 100 times, pin the answer on the board. "
        "The board gets stale if HR changes the policy and doesn't update it."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 7 — Content Delivery Network (CDN)
# ─────────────────────────────────────────────────────────────────────────────

_C7 = Concept(
    id    = "cdn",
    name  = "Content Delivery Network (CDN)",
    order = 7,
    book_pages = "pp. 13–16",

    core_facts = [
        "CDN: a network of geographically dispersed servers that deliver static content (images, videos, CSS, JS) to users from the nearest edge node.",
        "The further a user is from CDN servers, the slower the load — CDN reduces this by serving from the nearest location.",
        "CDN workflow: user requests asset → CDN checks cache → if absent, CDN fetches from origin (web server or S3) → caches with TTL → serves to user. Subsequent users get it from CDN cache.",
        "CDN considerations: Cost (third-party, charged per data transfer — don't cache infrequently used assets); Cache expiry (too long = stale content, too short = repeated origin fetches); CDN fallback (if CDN is down, clients must detect and fall back to origin); File invalidation before TTL expires (use APIs or object versioning e.g. image.png?v=2).",
        "Dynamic content CDN (caching HTML based on request path, cookies, headers) is an advanced topic — for most interviews, focus on static content CDN.",
    ],

    why_it_matters = (
        "Any globally distributed system — and every FAANG-level interview problem "
        "is globally distributed — needs a CDN answer. It is also the fastest win: "
        "moving static assets off your servers immediately reduces load and latency."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing the CDN workflow for static content delivery.

{SVG_STYLE_GUIDE}

Two sections:

SECTION 1 — "CDN improves load time" (top half):
- Two Client boxes on the left (Client A and Client B)
- One CDN node in the middle
- One Origin server on the right
- Client A → CDN arrow labelled "30ms" (close, fast)
- Client B → Origin arrow labelled "120ms" (far, slow, bypassing CDN)
- Caption: "Closer to CDN = faster delivery"

SECTION 2 — "CDN workflow" (bottom half):
- User A box (left)
- CDN box (centre)
- Origin Server box (right)

Numbered flow arrows:
1. User A → CDN: "① get image.png"
2. CDN → Origin: "② if not in CDN → fetch from origin" (dashed)
3. Origin → CDN: "③ store image.png in CDN" (dashed, green return)
4. CDN → User A: "④ return image.png"
5. User B (below User A) → CDN: "⑤ get image.png"
6. CDN → User B: "⑥ return from cache (TTL not expired)"

Small annotation: "TTL controls how long CDN holds the asset"

Footnote: "Figure 1-10 — CDN workflow: origin fetch on miss, cache hit for subsequent users"
""",

    diagram_type    = "reference",
    solicit_drawing = False,

    drawing_rubric = [],

    jordan_minimum_bar = (
        "Candidate must explain what CDN serves (static assets only in most cases), "
        "describe the basic workflow (miss → fetch from origin → cache → serve), "
        "and name at least two CDN considerations (cost, TTL, fallback, invalidation)."
    ),

    jordan_probes = [
        "What exactly does a CDN serve? Give me five examples of assets that belong there.",
        "Walk me through what happens the first time a user requests an image that isn't in the CDN yet.",
        "You updated your main CSS file. How do you make sure users aren't served the stale cached version?",
        "CDN goes down. What happens to your site?",
        "You're caching an image with a 30-day TTL and the image changes. What are your options?",
    ],

    common_mistakes = [
        "Thinking CDN caches dynamic API responses by default — it primarily serves static content.",
        "Not knowing about TTL and its role in cache freshness.",
        "Forgetting that CDN is a third-party cost — caching infrequently used assets wastes money.",
        "Not having a CDN fallback strategy — CDN outages happen.",
    ],

    faang_signal = (
        "Candidate mentions object versioning (image.png?v=2) as the preferred "
        "invalidation strategy and explains that CDN API-based invalidation is slower "
        "and charges per request at some providers."
    ),

    alex_analogy_seed = (
        "A global bookstore with regional distribution warehouses — instead of shipping "
        "every order from one central warehouse, you stock the popular titles locally "
        "so customers nearby get them in one day instead of two weeks."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 8 — Stateless Web Tier
# ─────────────────────────────────────────────────────────────────────────────

_C8 = Concept(
    id    = "stateless_web_tier",
    name  = "Stateless Web Tier",
    order = 8,
    book_pages = "pp. 17–19",

    core_facts = [
        "Stateful server: remembers client session data between requests. Problem: every request from the same client MUST go to the same server (sticky sessions), making scaling and failover much harder.",
        "Stateless server: keeps no session state. State is stored in a shared external data store (relational DB, Memcached/Redis, NoSQL). Any web server can handle any request.",
        "Stateless web tier is simpler, more robust, and scalable. Enables true autoscaling.",
        "Shared session store options: relational DB, Memcached, Redis, NoSQL (e.g. DynamoDB). NoSQL is often chosen for ease of horizontal scaling.",
        "Autoscaling: web servers can be added or removed automatically based on traffic load ONLY if they are stateless — because there is no session data to migrate.",
    ],

    why_it_matters = (
        "Autoscaling — adding and removing servers automatically — is impossible with "
        "stateful servers. This concept is the prerequisite for everything that makes "
        "modern cloud systems elastic. Jordan will probe this hard."
    ),

    diagram_prompt = f"""
Generate TWO side-by-side SVG diagrams contrasting stateful vs stateless architecture.

{SVG_STYLE_GUIDE}

LEFT SIDE — "Stateful (Problem)":
- Three user boxes (User A, User B, User C) on the far left
- Three server boxes in the middle (Server 1, Server 2, Server 3)
- Each user has a rigid arrow to ONE specific server only
  (User A → Server 1, User B → Server 2, User C → Server 3)
- Inside each server box: small label "Session data for User X"
- Label at bottom: "Sticky sessions required — hard to scale"
- Small ✗ icon

RIGHT SIDE — "Stateless (Solution)":
- Three user boxes (User A, User B, User C) on the far left
- A cluster of web server boxes in the middle (grouped in dashed box labelled "Web Servers — Auto Scale ①")
- Arrows from ALL users going to the CLUSTER (any server)
- Below the cluster: a single Shared Storage box (cylinder or DB icon)
  labelled "Shared State Store (Redis / NoSQL)"
- Arrow from cluster to shared storage: "fetch state"
- Label at bottom: "Any server handles any request — true autoscaling"
- Small ✓ icon

Dividing line between the two diagrams with label "vs"

Footnote: "Figure 1-13 / 1-14 — Stateful servers require sticky sessions; stateless servers scale freely"
""",

    diagram_type    = "evolution",   # shows before/after contrast
    solicit_drawing = True,

    drawing_rubric = [
        DrawingRubricItem(
            label       = "Stateless web servers shown",
            description = "Web server boxes are shown without local session storage; state is external.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Shared state store present",
            description = "An external shared storage (Redis, NoSQL, or DB) is shown as the session store.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Any server can handle any request",
            description = "Arrows from users go to the server cluster (not to specific servers), showing flexibility.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Autoscaling indicated",
            description = "The web server cluster is labelled or annotated as auto-scaling.",
            required    = False,
        ),
        DrawingRubricItem(
            label       = "Stateful problem identified",
            description = "Candidate's diagram or explanation contrasts with the stateful sticky-session problem.",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must correctly explain why stateful servers prevent autoscaling "
        "(sticky sessions bind users to specific servers), describe the stateless "
        "solution (shared external store), and name at least one technology for the store."
    ),

    jordan_probes = [
        "Draw me the stateless web tier. Where does session data live?",
        "Why can't you just autoscale a stateful server farm?",
        "What is a sticky session? What's wrong with relying on them?",
        "You store sessions in Redis. Redis goes down. What happens to logged-in users?",
        "Between Redis and a relational DB for session storage — which do you pick and why?",
    ],

    common_mistakes = [
        "Saying 'stateless' without explaining where the state actually goes.",
        "Not knowing what a sticky session is or why load balancers need to support them for stateful apps.",
        "Treating stateless as only a performance optimisation rather than a scaling prerequisite.",
        "Not considering the failure mode of the shared session store itself.",
    ],

    faang_signal = (
        "Candidate explains that stateless is not just about autoscaling but also about "
        "simplifying deployment — any server can be replaced without session migration — "
        "and proactively considers what happens when the shared store fails."
    ),

    alex_analogy_seed = (
        "A hospital where any nurse can treat any patient because all medical records "
        "are in a central system — vs one where each patient can only see their assigned "
        "nurse because only that nurse has the notes."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 9 — Data Centers & GeoDNS
# ─────────────────────────────────────────────────────────────────────────────

_C9 = Concept(
    id    = "data_centers",
    name  = "Data Centers & GeoDNS",
    order = 9,
    book_pages = "pp. 20–22",

    core_facts = [
        "Multiple data centres improve availability and reduce latency for globally distributed users.",
        "GeoDNS (geo-routing): routes users to the nearest data centre by resolving domain names to different IPs based on user location. Splits traffic e.g. x% to US-East, (100-x)% to US-West.",
        "Data centre failover: if DC2 goes offline, 100% of traffic is routed to DC1 automatically.",
        "Technical challenges: traffic redirection (GeoDNS handles this), data synchronisation (users in different regions may have different local data — common strategy: replicate across multiple data centres asynchronously, as Netflix does), test and deployment consistency (automated tools must deploy consistently across all DCs).",
        "Data synchronisation is the hardest challenge: in failover, traffic may be routed to a DC where the relevant user's data hasn't been replicated yet.",
    ],

    why_it_matters = (
        "Any system serving a global user base needs this conversation. Jordan will "
        "always ask 'what happens if an entire data centre goes down?' This is your answer."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing a two-data-centre setup with GeoDNS routing.

{SVG_STYLE_GUIDE}

Elements:

1. Top: User group box, DNS globe (top right), CDN cloud (far right)
   - Arrow from User to DNS: "www.mysite.com"
   - Arrow from User to CDN

2. Middle: Load Balancer box below DNS
   - Two dashed arrows FROM Load Balancer downward, forking left and right
   - Left arrow: "Geo-routed → DC1 US-East (x%)"
   - Right arrow: "Geo-routed → DC2 US-West ((100-x)%)"

3. Bottom-left dashed group: "DC1 US-East"
   Inside: Web Servers cluster, Databases cylinder, Caches box

4. Bottom-right dashed group: "DC2 US-West"
   Inside: Web Servers cluster, Databases cylinder, Caches box, NoSQL store

5. Dashed horizontal arrow between DC1 databases and DC2 databases:
   "Async replication" (green dashed)

6. Small annotation: "If DC2 goes offline → 100% traffic to DC1"

Footnote: "Figure 1-15 — Two data centres with GeoDNS routing and async DB replication"
""",

    diagram_type    = "reference",
    solicit_drawing = False,

    drawing_rubric = [],

    jordan_minimum_bar = (
        "Candidate must explain GeoDNS routing, describe what happens on a full data "
        "centre outage (100% failover to surviving DC), and identify data synchronisation "
        "as the hardest challenge in a multi-DC setup."
    ),

    jordan_probes = [
        "US-West data centre goes completely offline. Walk me through what happens.",
        "A user in London signs up. Which data centre gets their data? What if the London-closest DC fails?",
        "How does data get from DC1 to DC2? What are the risks of that approach?",
        "What is GeoDNS? How is it different from a regular load balancer?",
        "You need to test a deployment across both data centres simultaneously. How do you do that safely?",
    ],

    common_mistakes = [
        "Not knowing that GeoDNS routes by user location — confusing it with a standard load balancer.",
        "Underestimating the data synchronisation problem — this is the crux of multi-DC design.",
        "Not explaining what 'asynchronous replication' means or its consistency trade-off.",
        "Forgetting that deployment tooling must be consistent across all data centres.",
    ],

    faang_signal = (
        "Candidate identifies that async replication creates eventual consistency "
        "and explains the trade-off: strong consistency requires synchronous replication "
        "which increases write latency. Mentions CAP theorem by name."
    ),

    alex_analogy_seed = (
        "A bank with branches in New York and London. If the New York office closes, "
        "all customers are redirected to London — but London needs to have an up-to-date "
        "copy of every customer's account balance for that to work."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 10 — Message Queue
# ─────────────────────────────────────────────────────────────────────────────

_C10 = Concept(
    id    = "message_queue",
    name  = "Message Queue",
    order = 10,
    book_pages = "pp. 22–24",

    core_facts = [
        "A message queue is a durable component stored in memory that supports asynchronous communication between services.",
        "Producers (publishers) create messages and publish them to the queue. Consumers (subscribers) connect to the queue and perform actions defined by the messages.",
        "Producer and consumer are DECOUPLED — producer can post a message even when the consumer is unavailable. Consumer reads from the queue even when the producer is unavailable.",
        "Decoupling enables independent scaling of producer and consumer: when the queue grows, add more workers (consumers). When the queue is empty, reduce workers.",
        "Use case example: photo processing pipeline — web server (producer) posts photo jobs to queue; photo processing workers (consumers) pick them up asynchronously. Customization tasks take time; async approach prevents blocking the web server.",
    ],

    why_it_matters = (
        "Any time a task is too slow to complete synchronously in a web request — "
        "video encoding, email sending, ML inference — you need a message queue. "
        "Jordan uses this to test whether you know how to decouple systems."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing a message queue between producer and consumer.

{SVG_STYLE_GUIDE}

Elements (left to right):

1. Left: Producer box
   Label: "Producer"
   Sub-label: "(e.g. Web Servers)"

2. Centre: Message Queue box (wider than server boxes, with 3 envelope icons inside)
   Label: "Message Queue"
   Sub-label: "Durable, in-memory"

3. Right: Consumer box (or cluster of boxes to indicate scaling)
   Label: "Consumer"
   Sub-label: "(e.g. Photo Processing Workers)"

4. Arrows:
   - Producer → Queue: "publish" (solid arrow right)
   - Queue → Consumer: "consume" (solid arrow right)
   - Consumer → Queue: "subscribe" (dashed arrow back, showing subscription model)

5. Annotation box below the diagram:
   "Producer unavailable? Consumer still reads from queue."
   "Consumer unavailable? Producer still writes to queue."
   "Queue grows? Add more consumers."

6. Small concrete example inset (bottom right):
   Web server → [📷 job] → Queue → Photo Worker
   Label: "Async photo processing"

Footnote: "Figure 1-17/1-18 — Message queue decouples producer and consumer for async processing"
""",

    diagram_type    = "reference",
    solicit_drawing = False,

    drawing_rubric = [],

    jordan_minimum_bar = (
        "Candidate must explain producer-consumer decoupling, describe at least one "
        "real use case for a message queue in the context of the interview problem, "
        "and explain why the queue enables independent scaling of producers and consumers."
    ),

    jordan_probes = [
        "Your image processing is taking 30 seconds per photo. How do you handle that without blocking the user?",
        "Walk me through what happens if all your photo processing workers go down. What happens to the queue?",
        "Your queue is growing faster than workers can process it. What do you do?",
        "Why not just call the photo processing service directly from the web server?",
        "What's the difference between a message queue and a pub/sub system?",
    ],

    common_mistakes = [
        "Treating message queues as only a performance tool rather than a decoupling and reliability tool.",
        "Not explaining what happens to the queue when consumers are down (messages persist — durable).",
        "Not connecting the queue to the specific problem's slow operations.",
        "Confusing message queue with event streaming (Kafka) without explaining the difference.",
    ],

    faang_signal = (
        "Candidate identifies the specific slow operation in the interview problem that "
        "warrants a queue, explains the durability guarantee, and mentions that the queue "
        "size acts as a natural backpressure signal for autoscaling consumers."
    ),

    alex_analogy_seed = (
        "A restaurant order ticket system — the waiter (producer) drops the ticket "
        "in the kitchen queue and walks away. The chef (consumer) picks it up when ready. "
        "Neither blocks the other."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 11 — Database Sharding
# ─────────────────────────────────────────────────────────────────────────────

_C11 = Concept(
    id    = "database_sharding",
    name  = "Database Sharding (Horizontal DB Scaling)",
    order = 11,
    book_pages = "pp. 25–29",

    core_facts = [
        "Sharding separates a large database into smaller, more manageable pieces called shards. Each shard shares the same schema but holds a unique subset of data.",
        "Sharding key (partition key): one or more columns that determine which shard a row belongs to. Example: user_id % 4 → routes to shard 0, 1, 2, or 3.",
        "Choosing the sharding key is critical — it must allow even data distribution and efficient query routing.",
        "Problems with sharding: Resharding (when a single shard can no longer hold data; consistent hashing is a common solution); Celebrity/hotspot problem (one shard gets disproportionate traffic — e.g. all data for Katy Perry, Justin Bieber, Lady Gaga on the same shard); Join and de-normalisation (JOIN across shards is hard — common workaround is to de-normalise the database).",
        "Vertical scaling of databases: Amazon RDS can provide up to 24TB RAM — useful but has hardware limits and SPOF risk.",
        "Horizontal scaling (sharding) is the solution for very large datasets that exceed what one machine can store.",
    ],

    why_it_matters = (
        "When your database grows beyond a single machine, sharding is the answer. "
        "Jordan expects you to know the problems sharding introduces — not just that "
        "it exists. The celebrity problem and resharding are favourite probes."
    ),

    diagram_prompt = f"""
Generate an SVG architecture diagram showing sharded databases with a hash function router.

{SVG_STYLE_GUIDE}

Elements (top to bottom):

1. Top: a decision diamond or router box labelled "user_id % 4" 
   Sub-label: "Sharding Key: user_id"

2. Below the router: four database cylinders in a row, labelled:
   "Shard 0", "Shard 1", "Shard 2", "Shard 3"
   Each with a small table inside showing sample user_ids:
   - Shard 0: 0, 4, 8, 12
   - Shard 1: 1, 5, 9, 13
   - Shard 2: 2, 6, 10, 14
   - Shard 3: 3, 7, 11, 15

3. Arrows from router to each shard (fan-out from decision box)

4. Three annotation callout boxes connected to the diagram with dashed lines:
   - "⚠ Resharding: shard exhausted → consistent hashing"
   - "⚠ Celebrity: one shard overloaded → allocate dedicated shard"
   - "⚠ Joins: cross-shard joins are expensive → de-normalise"

Footnote: "Figure 1-21/1-22 — Sharding routes by user_id % 4; each shard holds unique rows"
""",

    diagram_type    = "reference",
    solicit_drawing = True,

    drawing_rubric = [
        DrawingRubricItem(
            label       = "Sharding function shown",
            description = "A hash function or partition logic (e.g. user_id % N) is shown routing data to shards.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Multiple shards present",
            description = "At least 2 shard databases are drawn.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Sharding key identified",
            description = "The candidate labels or annotates the sharding key used.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "At least one sharding problem noted",
            description = "Resharding, celebrity problem, or join difficulty is annotated on the diagram.",
            required    = False,
        ),
        DrawingRubricItem(
            label       = "Even data distribution indicated",
            description = "Sample data or annotation shows data is distributed evenly across shards.",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must explain the sharding key concept, describe how data is routed "
        "to the correct shard, and identify at least two of the three sharding problems "
        "(resharding, celebrity/hotspot, join difficulty)."
    ),

    jordan_probes = [
        "Draw the sharding architecture. Show me how you'd route a query for user_id 7.",
        "Lady Gaga, Justin Bieber, and Katy Perry all have user_ids that hash to shard 2. What happens?",
        "Shard 3 is at 90% capacity and growing. What do you do?",
        "I need to run a JOIN across users in shard 0 and orders in shard 2. How do you handle that?",
        "What is consistent hashing and why is it relevant here?",
        "How do you choose a sharding key? What makes a bad sharding key?",
    ],

    common_mistakes = [
        "Not knowing the three main sharding problems (resharding, celebrity, joins).",
        "Saying sharding is 'just partitioning' without explaining the routing mechanism.",
        "Not mentioning consistent hashing as the solution to resharding.",
        "Choosing a sharding key without considering hotspot risk.",
    ],

    faang_signal = (
        "Candidate explains consistent hashing unprompted as the standard solution to "
        "resharding, and suggests per-celebrity shard allocation as the solution to the "
        "hotspot problem rather than a naive hash function."
    ),

    alex_analogy_seed = (
        "A library split across four buildings, each holding books whose catalogue number "
        "ends in 0-3. You always know which building to go to. But if one building gets "
        "all the bestsellers, the queues there become impossible."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 12 — Full Architecture Capstone (Figure 1-23)
# ─────────────────────────────────────────────────────────────────────────────

_C12 = Concept(
    id    = "full_architecture",
    name  = "Full Architecture — Millions of Users",
    order = 12,
    book_pages = "pp. 29–30",

    core_facts = [
        "The complete architecture for millions of users combines all previous concepts into a coherent layered system.",
        "Summary of techniques (book's closing list): Keep web tier stateless; Build redundancy at every tier; Cache data as much as possible; Support multiple data centres; Host static assets in CDN; Scale data tier by sharding; Split tiers into individual services; Monitor the system and use automation tools.",
        "Logging, metrics, and automation are essential at scale: per-server error logs, aggregated tier metrics (DB performance, cache hit rate), key business metrics (DAU, retention, revenue), and CI/CD automation.",
        "The system includes: DNS → CDN → Load Balancer → Stateless Web Tier (autoscaling) → Message Queue → Workers → Sharded DBs + Caches + NoSQL → Tools (Logging, Monitoring, Metrics, Automation).",
    ],

    why_it_matters = (
        "Jordan's final ask in almost every interview is 'draw me the full system'. "
        "This is your chance to demonstrate that you can hold the whole architecture "
        "in your head and explain how the pieces fit together."
    ),

    diagram_prompt = f"""
Generate a comprehensive SVG architecture diagram showing the full scaled system from the book (Figure 1-23 equivalent).

{SVG_STYLE_GUIDE}

This is the most complex diagram. Layout top-to-bottom, left-to-right:

ROW 1 (top):
- User group box (laptop + phone)
- DNS globe (top right, arrow FROM user)
- CDN cloud (top right, arrow FROM user for static assets)

ROW 2:
- Load Balancer box (centred, below User)
  Arrow FROM user to LB, arrow FROM DNS back to user with IP

ROW 3 — Web Tier (dashed group box labelled "Web Tier — Stateless ① Auto Scale"):
- Three server boxes side by side (Server 1, Server 2, Server 3)
- Arrow FROM LB fanning to all three

ROW 3 — Message Queue (right of Web Tier):
- Message Queue box with 3 envelope icons
- Arrow FROM Web Servers TO Queue

ROW 4 (left) — Data Tier (dashed group box labelled "Data Tier"):
- Sharded DBs: three cylinder icons in a row labelled "Shard 1", "Shard 2", "Shard 3"
  Under shared label: "① Databases"
- Cache cluster: three cache boxes labelled "Cache" (stacked, labelled "Caches")
- NoSQL store: labelled "② NoSQL" (for session data)
- Replication arrows between shard cylinders (green dashed horizontal)

ROW 4 (right) — Workers (dashed group box):
- Three small server boxes labelled "Workers"
- Arrow FROM Queue TO Workers

ROW 5 (bottom) — Tools:
- Four boxes in a row: "Logging", "Metrics", "Monitoring", "Automation"
- Grouped under label "② Tools"
- Dashed upward arrow to Data Tier indicating monitoring

DC1 dashed outer box around rows 3-5 labelled "DC1 (US-East)"
Note at bottom: "DC2 (US-West) mirrors this setup with async replication"

Footnote: "Figure 1-23 — Full system: supports millions of users"
""",

    diagram_type    = "reference",
    solicit_drawing = True,   # Jordan's capstone ask

    drawing_rubric = [
        DrawingRubricItem(
            label       = "DNS and CDN present",
            description = "DNS and CDN are shown at the top of the diagram.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Load balancer present",
            description = "Load balancer is shown between users and web tier.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Stateless web tier with multiple servers",
            description = "Web tier shows multiple servers with no local session state.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Message queue present",
            description = "A message queue is shown decoupling web servers from workers.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Sharded databases",
            description = "Database layer shows multiple shards or a sharding mechanism.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Cache tier present",
            description = "A cache layer (Redis / Memcached) is shown between web tier and DB.",
            required    = True,
        ),
        DrawingRubricItem(
            label       = "Multiple data centres indicated",
            description = "The diagram references multi-DC or geo-routing.",
            required    = False,
        ),
        DrawingRubricItem(
            label       = "Monitoring / logging tools shown",
            description = "A tools or observability layer is included.",
            required    = False,
        ),
    ],

    jordan_minimum_bar = (
        "Candidate must draw a coherent layered architecture that includes: load balancer, "
        "stateless web tier, cache, database replication or sharding, and CDN. "
        "Must be able to narrate data flow from user request to database and back."
    ),

    jordan_probes = [
        "Draw me the full system. Walk me through a user request from browser to database.",
        "Point to the single biggest bottleneck in your diagram right now.",
        "Traffic just 10x'd overnight. Walk me through every layer and how it handles that.",
        "What does 'build redundancy at every tier' mean in your diagram? Show me where redundancy is missing.",
        "How does your monitoring layer know that Shard 2 is running hot?",
        "You're being asked to support 1 billion users next year. Which part of your diagram breaks first?",
    ],

    common_mistakes = [
        "Drawing a diagram with the right components but no data flow labels — Jordan wants to see the narration.",
        "Forgetting the message queue / async workers layer when the problem has slow operations.",
        "Not including monitoring/logging — at scale, you can't operate what you can't observe.",
        "Treating the full diagram as additive rather than integrated — components must connect logically.",
    ],

    faang_signal = (
        "Candidate draws the full diagram fluently, labels data flows directionally, "
        "proactively identifies the next bottleneck to address, and explains the "
        "monitoring strategy without being asked."
    ),

    alex_analogy_seed = (
        "A city's entire infrastructure — water supply, power grid, road network, "
        "hospitals, communication towers — all designed to keep working when any "
        "single component fails."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Exported curriculum
# ─────────────────────────────────────────────────────────────────────────────

CHAPTER_1_CONCEPTS: list[Concept] = [
    _C1,   # Single Server Setup
    _C2,   # Database Tier Separation
    _C3,   # Vertical vs Horizontal Scaling
    _C4,   # Load Balancer
    _C5,   # Database Replication
    _C6,   # Cache Tier
    _C7,   # CDN
    _C8,   # Stateless Web Tier
    _C9,   # Data Centers & GeoDNS
    _C10,  # Message Queue
    _C11,  # Database Sharding
    _C12,  # Full Architecture Capstone
]

# Lookup by id — used by engine and routes
CONCEPT_BY_ID: dict[str, Concept] = {c.id: c for c in CHAPTER_1_CONCEPTS}

# Concepts that require candidate drawings — used to activate whiteboard UI
DRAWING_CONCEPTS: list[Concept] = [c for c in CHAPTER_1_CONCEPTS if c.solicit_drawing]

# Ordered concept ids — used by teach sequencer
CONCEPT_ORDER: list[str] = [c.id for c in CHAPTER_1_CONCEPTS]
