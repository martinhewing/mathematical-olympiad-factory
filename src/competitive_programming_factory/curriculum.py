"""
connectionsphere_factory/curriculum.py  —  COMPETITIVE PROGRAMMING INSTANCE

Chapter 1 — Jugs, Stamps, and How to Solve Problems
Source: First Step to Mathematical Olympiad Problems (Mathematical Olympiad Series),
        Derek Holton, Chapter 1, pp. 1–26

This module is the single source of truth for the TEACH phase and Jordan's
interview probes. Nothing here is generated at runtime — it is hard-coded from
the book and reviewed for accuracy.

Claude's role is ENRICHMENT ONLY:
  - Vary the analogy Alex uses to explain each concept
  - Personalise the comprehension-check question wording
  - Generate the reference SVG diagram for each concept (cached globally)

Mathematical notation is expressed in LaTeX and must be rendered by the UI
using KaTeX or MathJax.  Inline math: $...$   Display math: $$...$$

Structure of each concept entry:
  id                  — stable key for caching, routing, and rubric lookup
  name                — display name shown in the UI
  order               — teach sequence (1-indexed, matches book progression)
  core_facts          — distillation of the book's key points;
                        Alex MUST cover all of these; Claude cannot omit or alter them
  why_it_matters      — the "so what" Alex leads with; grounds the concept in reality
  book_pages          — page reference for traceability
  diagram_prompt      — instruction passed to Claude to generate the reference SVG
  diagram_type        — "reference" | "evolution" | "proof_flow"
  solicit_drawing     — True = Alex asks candidate to sketch/prove; Jordan will probe it
  drawing_rubric      — elements the candidate's proof or sketch MUST contain
  jordan_minimum_bar  — lowest acceptable answer before Jordan flags the stage
  jordan_probes       — exact follow-up questions Jordan uses, in escalation order
  common_mistakes     — what weak candidates say; used to calibrate Jordan's scoring
  faang_signal        — what a strong hire signal looks like on this concept
  alex_analogy_seed   — hint to Claude for the real-world analogy to use
"""

from __future__ import annotations

from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# Data model  (identical schema to the System Design instance)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DrawingRubricItem:
    label: str  # short name shown in UI feedback
    description: str  # what Claude checks for in the candidate's work
    required: bool  # True = must be present for PASS; False = nice-to-have


@dataclass
class Concept:
    id: str
    name: str
    order: int
    core_facts: list[str]
    why_it_matters: str
    book_pages: str
    diagram_prompt: str
    diagram_type: str  # "reference" | "evolution" | "proof_flow"
    solicit_drawing: bool
    drawing_rubric: list[DrawingRubricItem]
    jordan_minimum_bar: str
    jordan_probes: list[str]
    common_mistakes: list[str]
    faang_signal: str
    alex_analogy_seed: str


# ─────────────────────────────────────────────────────────────────────────────
# SVG style guide — injected into every diagram_prompt
# ─────────────────────────────────────────────────────────────────────────────

SVG_STYLE_GUIDE = """
SVG constraints (enforce strictly):
- viewBox="0 0 680 420", xmlns="http://www.w3.org/2000/svg"
- Background: rect fill="#0f1117"
- Boxes: rect rx="6", fill="#1e2130", stroke="#3a3f55", stroke-width="1.5"
- Primary arrows: stroke="#6c8ebf", stroke-width="1.5", marker-end="url(#arrow)"
- Highlight / proof arrows: stroke="#5a9e6f" (green), stroke-width="1.2",
  stroke-dasharray="5,3"
- Warn / counterexample arrows: stroke="#c97c4a" (amber), stroke-width="1.2",
  stroke-dasharray="4,3"
- Labels inside boxes: font-family="'DM Mono', monospace", font-size="12",
  fill="#c9d1d9"
- Sub-labels / case annotations: font-size="10", fill="#8b949e"
- Section grouping labels: font-size="11", fill="#6e7681", font-style="italic"
- Dashed group boundaries: rect stroke="#3a3f55", stroke-dasharray="6,3",
  fill="none", rx="8"
- Math expressions INSIDE SVG text elements: render as plain Unicode
  approximations (e.g. "n ≥ 8", "3a + 5b", "gcd(r,s) = 1") — actual LaTeX
  rendering is handled by the UI layer outside the SVG.
- Define arrowhead marker:
    <marker id="arrow" markerWidth="8" markerHeight="8"
      refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#6c8ebf"/>
    </marker>
- No drop shadows. No gradients. No colour fills on boxes.
- All text horizontally centred within its box.
- Minimum padding inside boxes: 10px on all sides.
- Do NOT include DOCTYPE, xml declaration, or <html> tags.
- Return raw SVG only — nothing else.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Concept 1 — The Problem-Solving Framework
# ─────────────────────────────────────────────────────────────────────────────

_C1 = Concept(
    id="problem_solving_framework",
    name="The Problem-Solving Framework",
    order=1,
    book_pages="pp. 3–5",
    core_facts=[
        "A problem is something you have no idea how to solve at first sight. Once solved, it is no longer a problem for you.",
        "Step (a) — Take one problem: focus entirely on a single, precisely stated problem before attempting generalisations.",
        "Step (b) — Read and understand: re-read several times; identify what is actually being asked, not a similar question you wish had been asked.",
        "Step (c) — Important words: change a word or number in the problem. If the change alters the problem, that word or number is critical.",
        "Step (d) — Panic and explore: doodle, try examples, ask 'have I seen something like this before?' It is normal to feel lost. Try small cases.",
        "Step (e) — System: use tables, charts, and diagrams. Never discard scratch work — a pattern you noticed earlier may become the key.",
        "Step (f) — Patterns: recognise and exploit structure. Pattern-recognition is one of mathematics' primary powers.",
        "Step (g) — Guess: form conjectures. Mathematicians call guesses conjectures — it is the same thing with a Latin name.",
        "Step (h) — Mathematical technique: deploy the right algebraic, number-theoretic, or combinatorial tools once the structure is clear.",
        "Step (i) — Explanations: write out the solution formally. The act of writing often exposes gaps or a neater route.",
        "Step (j) — Generalise: once one problem is solved, ask what the broader class of problems looks like.",
    ],
    why_it_matters=(
        "Every hard competitive-programming problem feels impossible until it doesn't. "
        "The difference between candidates who make progress and those who freeze is "
        "whether they have a systematic fallback when the answer isn't obvious. "
        "Jordan is not just testing whether you know the answer — Jordan is watching "
        "how you behave when you don't."
    ),
    diagram_prompt=f"""
Generate an SVG flowchart of the Holton problem-solving framework.

{SVG_STYLE_GUIDE}

Layout: a vertical flowchart with ten step boxes, connected by downward arrows.
Each box is labelled with the step letter and a short name.

Boxes (top to bottom):
  (a) Take one problem
  (b) Read & understand
  (c) Hunt key words
  (d) Panic & explore
  (e) Be systematic
  (f) Find patterns
  (g) Conjecture
  (h) Apply technique
  (i) Write the proof
  (j) Generalise

Arrows:
  - Solid downward arrows connecting each consecutive step.
  - A dashed green curved arrow from box (g) back up to box (d)
    labelled "conjecture fails → re-explore"
  - A dashed green curved arrow from box (j) looping back to box (a)
    labelled "new problem"

Colour accent: box (d) has a slightly brighter border (#c97c4a amber) to
signal "this is where most candidates freeze".

Footnote: "Figure 1-0 — Holton's ten-step problem-solving framework (§1.3)"
""",
    diagram_type="reference",
    solicit_drawing=False,
    drawing_rubric=[],
    jordan_minimum_bar=(
        "Candidate must articulate at least five of the ten steps in their own words "
        "and give a concrete example of when 'step (d) panic and explore' led to a "
        "breakthrough by trying small cases."
    ),
    jordan_probes=[
        "You're ten minutes into a problem and have no idea how to start. Walk me through what you actually do.",
        "What does 'hunt the key words' mean in practice? Give me an example from today's problem.",
        "You've formed a conjecture. It passed five examples. Should you stop there? Why or why not?",
        "What is the difference between a conjecture and a theorem?",
        "You solved the problem. What does step (j) ask you to do next, and why should you bother?",
        "When does writing out a solution formally reveal a flaw that examples didn't catch?",
    ],
    common_mistakes=[
        "Attempting generalisation before fully solving the base case.",
        "Skipping small examples because the problem 'looks like' a known technique.",
        "Treating a conjecture verified on a few cases as a proof.",
        "Abandoning scratch work when switching approach — losing potentially useful patterns.",
    ],
    faang_signal=(
        "Candidate demonstrates the framework live during the session: explicitly names "
        "the step they are on, backtracks gracefully when a conjecture fails, and "
        "proactively generalises after solving the specific instance."
    ),
    alex_analogy_seed=(
        "A detective arriving at a crime scene: they don't sprint to conclusions — "
        "they gather evidence systematically, form hypotheses, test them, and write "
        "up findings only when the case is airtight."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 2 — The Jug Problem: Exploration and Efficiency
# ─────────────────────────────────────────────────────────────────────────────

_C2 = Concept(
    id="jug_problem",
    name="The Jug Problem: Exploration and Efficiency",
    order=2,
    book_pages="pp. 2–6",
    core_facts=[
        "Problem: using a 3-litre jug and a 5-litre jug, measure exactly 7 litres.",
        "Naïve approach: fill the 3L jug repeatedly and empty into the 5L jug, discarding the overflow. This requires 14 fills of the 3L jug and wastes water. Algebraically: $7 = 14 \\times 3 - 7 \\times 5$.",
        "Efficient approach: fill the 5L jug twice and discard one 3L measure. Only 3 litres of water is wasted. Algebraically: $7 = 2 \\times 5 - 1 \\times 3$.",
        "General principle: any integer $m$ can be expressed as $m = a \\times 3 + b \\times 5$ for integers $a, b$ (possibly negative). Negative coefficients mean 'discard that many jug-fulls'.",
        "Minimising jug usage means finding the representation $m = ar + bs$ where $|a| + |b|$ is smallest.",
        "Key observation: $1 = 2 \\times 3 - 1 \\times 5$, which is the Bézout identity for 3 and 5. Once you can make 1 from $r$ and $s$, you can make any integer multiple.",
    ],
    why_it_matters=(
        "The jug problem is the gateway to number theory. The moment you write "
        "$7 = 2 \\times 5 - 1 \\times 3$ you are doing Bézout's identity without "
        "knowing it. Jordan will use this problem to check whether you understand "
        "linear combinations before introducing the formal theorem."
    ),
    diagram_prompt=f"""
Generate an SVG diagram illustrating the two jug-solution strategies side by side.

{SVG_STYLE_GUIDE}

Layout: two panels, left and right, separated by a vertical divider labelled "vs".

LEFT PANEL — "Naïve: fill 3L repeatedly":
- A column of 14 small identical jug icons (simplified rectangle), labelled "×14"
- One large "discard" icon (wastebasket outline) with label "7 × 5L discarded"
- Caption below: "7 = 14×3 - 7×5   (expensive)"
- Amber border / small ✗ icon.

RIGHT PANEL — "Efficient: fill 5L twice":
- Two 5L jug icons
- One 3L jug icon with a downward arrow labelled "discard once"
- Caption below: "7 = 2×5 - 1×3   (minimal waste)"
- Green border / small ✓ icon.

Below both panels: a single centred annotation box:
  "In general: m = a×r + b×s  (a, b ∈ ℤ)"
  "Negative coefficient = discard that many jug-fulls"

Footnote: "Figure 1-2 — Jug problem: two strategies; only the coefficient signs change"
""",
    diagram_type="evolution",
    solicit_drawing=False,
    drawing_rubric=[],
    jordan_minimum_bar=(
        "Candidate must write the efficient algebraic representation $7 = 2 \\times 5 - 1 \\times 3$ "
        "and explain what a negative coefficient means physically (discarding water). "
        "Must connect this to the idea that any integer expressible as $ar + bs$ can be "
        "obtained with two coprime jugs."
    ),
    jordan_probes=[
        "Write me the algebraic identity behind the efficient jug solution.",
        "What does a negative coefficient mean in the context of measuring water?",
        "I give you a 4L jug and an 8L jug. Can you measure exactly 7 litres? Why or why not?",
        "What is the minimum number of jug-operations to produce 73 litres from a 3L and a 5L jug?",
        "Why does the fact that $\\gcd(3, 5) = 1$ matter here?",
    ],
    common_mistakes=[
        "Not recognising that negative coefficients are valid (pouring away is allowed).",
        "Believing any two jug sizes can produce any amount — missing the GCD condition.",
        "Confusing 'number of litres wasted' with 'number of jug operations'.",
        "Not generalising from the specific case to $m = ar + bs$ with integers $a, b$.",
    ],
    faang_signal=(
        "Candidate immediately writes $1 = 2 \\times 3 - 1 \\times 5$ and notes that "
        "this Bézout identity is the key: once you can make 1, you can make any $m$ "
        "by multiplying through. Connects this to GCD without being prompted."
    ),
    alex_analogy_seed=(
        "A change-making problem: if you only have 3p and 5p coins, how do you make "
        "exactly 7p? You can give change back — handing 5p back is the 'discard' operation."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 3 — Bézout's Identity and Integer Linear Combinations
# ─────────────────────────────────────────────────────────────────────────────

_C3 = Concept(
    id="bezout_identity",
    name="Bézout's Identity and Integer Linear Combinations",
    order=3,
    book_pages="pp. 6–8",
    core_facts=[
        "Theorem (Bézout): if $c$ and $d$ are positive integers with $\\gcd(c, d) = 1$, "
        "then there exist integers $a$ and $b$ such that $ac + bd = 1$.",
        "The pair $(a, b)$ is not unique. If $(a_0, b_0)$ is one solution, then "
        "$(a_0 + ds, b_0 - cs)$ is a solution for every integer $s$.",
        "Multiplying both sides by any integer $m$: if $\\gcd(c, d) = 1$, then "
        "$m = (ma)c + (mb)d$ — every integer $m$ is an integer linear combination of $c$ and $d$.",
        "More generally: for any $c, d$ with $\\gcd(c, d) = t$, there exist integers $a, b$ "
        "with $ac + bd = t$. The values expressible as $ar + bs$ (with $a, b \\geq 0$, non-negative) "
        "are exactly the multiples of $t$, beyond a certain threshold.",
        "When jugs have a common factor: $r = 2$, $s = 4$, $\\gcd = 2$ — only even volumes "
        "can be measured. $m$ must be a multiple of $\\gcd(r, s)$ to be achievable.",
    ],
    why_it_matters=(
        "Bézout's identity is the engine behind every result in this chapter. "
        "Every theorem about what stamp values or jug volumes are achievable reduces "
        "to asking whether a certain linear combination exists. Jordan will ask you "
        "to state and prove it in at most three lines."
    ),
    diagram_prompt=f"""
Generate an SVG diagram illustrating Bézout's identity and the family of solutions.

{SVG_STYLE_GUIDE}

Layout: two sections stacked vertically.

TOP SECTION — "The identity":
  - A centred display box containing the equation:
      ac + bd = 1   (gcd(c,d) = 1)
  - Two example rows below it:
      c=3, d=5:   2×3 + (-1)×5 = 1
      c=4, d=13:  (-3)×4 + 1×13 = 1
  - Arrow from each example row to a small tick.

BOTTOM SECTION — "The family of solutions":
  - A horizontal number line labelled with integers from -3 to 10.
  - The solution (a₀, b₀) = (2, -1) is marked with a filled dot at position a=2.
  - Three other solutions are marked with open dots:
      a = 2+5 = 7  (s=1),  a = 2+10 = 12 (s=2),  a = 2-5 = -3 (s=-1)
  - A horizontal arrow across the number line labelled "+d steps → another solution"
  - Below the number line: "a = a₀ + ds,  b = b₀ - cs  for any integer s"

Small callout box (bottom-right):
  "If gcd(r,s) = t: only multiples of t are achievable"

Footnote: "Figure 1-3 — Bézout: one solution generates infinitely many; GCD governs what's reachable"
""",
    diagram_type="reference",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Theorem statement written",
            description="Candidate writes 'if gcd(c,d)=1 then there exist integers a,b with ac+bd=1'.",
            required=True,
        ),
        DrawingRubricItem(
            label="Concrete example verified",
            description="At least one explicit pair (a,b) is computed and verified (e.g. 2×3-1×5=1).",
            required=True,
        ),
        DrawingRubricItem(
            label="General solution family stated",
            description="Candidate states that (a+ds, b-cs) gives all solutions for integer s.",
            required=True,
        ),
        DrawingRubricItem(
            label="GCD generalisation noted",
            description="Candidate addresses what happens when gcd(c,d) = t > 1.",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must state Bézout's theorem correctly (including the coprimality "
        "hypothesis), find a concrete Bézout pair for $c=3, d=5$, and explain why "
        "the result fails when $\\gcd(c, d) > 1$."
    ),
    jordan_probes=[
        "State Bézout's identity precisely. What is the hypothesis you need?",
        "Find all integer pairs $(a, b)$ such that $4a + 11b = 1$.",
        "I give you jugs of size 6 and 9. Can you measure exactly 1 litre? What about 3 litres?",
        "Why is the solution pair $(a, b)$ not unique? How many solutions are there?",
        "How does Bézout's identity immediately tell you that any integer $m$ can be expressed as $ac + bd$ when $\\gcd(c,d) = 1$?",
        "Sketch a proof of Bézout's identity — you don't need to be fully rigorous.",
    ],
    common_mistakes=[
        "Forgetting that $a$ and $b$ can be negative — candidates look for positive solutions only.",
        "Stating the theorem without the coprimality hypothesis.",
        "Not knowing how to generate the full family of solutions from one particular solution.",
        "Failing to connect the GCD to what is achievable — thinking any two jug sizes work.",
    ],
    faang_signal=(
        "Candidate sketches the proof via the Well-Ordering Principle or Euclidean "
        "Algorithm without prompting, identifies the general family of solutions "
        "$(a_0 + ds, b_0 - cs)$ correctly, and immediately deduces the GCD "
        "divides everything reachable."
    ),
    alex_analogy_seed=(
        "A combination lock where each dial moves in steps of $c$ or $d$. "
        "If $\\gcd(c,d) = 1$, you can eventually reach any number on the dial. "
        "If $\\gcd(c,d) = 2$, you can only reach even numbers — you are stuck."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 4 — The Consecutive Numbers Problem
# ─────────────────────────────────────────────────────────────────────────────

_C4 = Concept(
    id="consecutive_numbers",
    name="The Consecutive Numbers Problem",
    order=4,
    book_pages="pp. 7–11",
    core_facts=[
        "Problem: find all sequences of consecutive positive integers that sum to 1000. Is any such sequence unique?",
        "A run of $k+1$ consecutive integers starting at $a$ has sum: "
        "$$a + (a+1) + \\cdots + (a+k) = \\tfrac{1}{2}(2a+k)(k+1).$$",
        "Setting this equal to $N$ gives $(2a+k)(k+1) = 2N$. For $N = 1000$: $(2a+k)(k+1) = 2000$.",
        "Since $k+1 \\geq 2$ is the number of terms and $2a+k \\geq 1$, "
        "we need to find all factorisations $2000 = PQ$ where $P = k+1$ and $Q = 2a+k$ "
        "have opposite parities (one odd, one even) and $Q > P$ (to keep $a \\geq 1$).",
        "Two consecutive integers always have opposite parity, so their sum is odd. "
        "Three consecutive integers: sum $\\equiv 0 + 1 + 2 = 0 \\pmod{3}$. "
        "This parity reasoning quickly eliminates many cases.",
        "For $N = 1000$: the odd factors of 2000 are 1, 5, 25, 125. "
        "These yield the valid runs: $\\{55,\\ldots,70\\}$ (16 terms), "
        "$\\{198,199,200,201,202\\}$ (5 terms), $\\{28,\\ldots,52\\}$ (25 terms).",
    ],
    why_it_matters=(
        "This problem is the canonical example of algebraic reformulation: a question "
        "that looks like it needs brute-force search collapses to a factorisation problem "
        "once you write the right equation. Jordan uses it to test whether you can "
        "spot the algebraic structure hiding in an arithmetic question."
    ),
    diagram_prompt=f"""
Generate an SVG diagram illustrating the consecutive-numbers algebraic approach.

{SVG_STYLE_GUIDE}

Layout: three rows.

ROW 1 — "The sum formula":
  - A wide centred box containing the arithmetic-progression formula:
      "Sum = ½(2a + k)(k + 1)"
  - Arrow pointing right to a smaller box: "= N"
  - Below: "(2a + k)(k + 1) = 2N"

ROW 2 — "Factorisation table" for N=1000:
  - A small table (4 columns × 5 rows) inside a dashed box:
      Header: k+1 | 2a+k | a | Valid?
      Row 1:  5   | 400  | —  | ✗ (400 odd, 5 odd — same parity)
      Row 2:  5   | 400  | 198 | ✓  ← highlight green
      Row 3:  16  | 125  | 55  | ✓  ← highlight green
      Row 4:  25  | 80   | 28  | ✓  ← highlight green
      Row 5:  400 | 5    | —   | ✗ (a would be negative)
  - Annotation: "Only odd×even factorisations of 2000 give integer a ≥ 1"

ROW 3 — "Parity rule":
  - Two side-by-side mini boxes:
      Left:  "k+1 odd  →  2a+k even"
      Right: "k+1 even →  2a+k odd"
  - Annotation below: "Always opposite parity — filters most cases immediately"

Footnote: "Figure 1-4 — Consecutive sum = factorisation problem: (2a+k)(k+1) = 2N"
""",
    diagram_type="proof_flow",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Sum formula derived",
            description="Candidate writes the arithmetic-progression sum formula correctly.",
            required=True,
        ),
        DrawingRubricItem(
            label="Equation set to N",
            description="Candidate sets (2a+k)(k+1) = 2N and identifies this as a factorisation problem.",
            required=True,
        ),
        DrawingRubricItem(
            label="Parity argument used",
            description="Candidate uses parity to eliminate invalid factorisation cases.",
            required=True,
        ),
        DrawingRubricItem(
            label="At least one valid run found for N=1000",
            description="Candidate produces at least one correct consecutive sequence summing to 1000.",
            required=True,
        ),
        DrawingRubricItem(
            label="All valid runs identified",
            description="Candidate finds all three valid runs (5, 16, 25 terms).",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must derive the arithmetic-progression sum formula, reduce the "
        "problem to $(2a+k)(k+1) = 2N$, apply the parity constraint, and find "
        "at least one valid consecutive run for $N = 1000$."
    ),
    jordan_probes=[
        "Write the sum of $k+1$ consecutive integers starting at $a$ as a closed formula.",
        "Why does the factorisation have to involve one odd factor and one even factor?",
        "Prove that the sum of exactly two consecutive integers is always odd.",
        "How many consecutive-integer representations does 1000 have? Enumerate them.",
        "Which positive integers have a UNIQUE consecutive-integer representation? Which have none?",
        "Powers of 2 cannot be written as a sum of consecutive positive integers. Why?",
    ],
    common_mistakes=[
        "Writing the sum as $a(k+1) + \\binom{k+1}{2}$ without simplifying to the closed form.",
        "Not applying the parity filter — generating many invalid cases instead.",
        "Allowing $a = 0$ (zero is not a positive integer in this context).",
        "Failing to check that $a \\geq 1$ after finding a factorisation.",
    ],
    faang_signal=(
        "Candidate immediately recognises that $N$ must have an odd factor greater than 1 "
        "to have any consecutive-integer representation, and deduces that powers of 2 "
        "have none — without being asked. Then characterises which $N$ have a unique "
        "representation."
    ),
    alex_analogy_seed=(
        "Stacking blocks in a staircase shape: the total number of blocks is the sum "
        "of consecutive integers. How many staircase shapes can you make with exactly "
        "1000 blocks? Each valid factorisation is one staircase."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 5 — The Stamp Problem: Discovery by Systematic Exploration
# ─────────────────────────────────────────────────────────────────────────────

_C5 = Concept(
    id="stamp_problem_discovery",
    name="The Stamp Problem: Discovery by Systematic Exploration",
    order=5,
    book_pages="pp. 9–12",
    core_facts=[
        "Problem: a post office has only 3¢ and 5¢ stamps. Which amounts of postage can it sell?",
        "Unlike the jug problem, stamps can only be 'added on' — we need $n = 3a + 5b$ "
        "with $a, b \\geq 0$ (non-negative integers). Negative coefficients are not valid here.",
        "Systematic table (amounts 1–10):\n"
        "  1: ✗   2: ✗   3: ✓ (1×3)   4: ✗   5: ✓ (1×5)\n"
        "  6: ✓ (2×3)   7: ✗   8: ✓ (1×3+1×5)   9: ✓ (3×3)   10: ✓ (2×5)",
        "The last failure is at $n = 7$. From 8 onwards every amount is achievable.",
        "Conjecture 1: every amount $n \\geq 8$ can be obtained with 3¢ and 5¢ stamps.",
        "Key structural difference from the jug problem: the jug problem allows negative "
        "coefficients; the stamp problem requires non-negative coefficients. "
        "This constraint makes the question harder — and more interesting.",
    ],
    why_it_matters=(
        "The stamp problem is the canonical instance of the Frobenius/coin problem. "
        "The systematic table is the entry point: without it, candidates guess at the "
        "threshold. With it, the conjecture is obvious — and Jordan will push you to "
        "prove it, not just state it."
    ),
    diagram_prompt=f"""
Generate an SVG diagram showing the stamp achievability table and the conjecture.

{SVG_STYLE_GUIDE}

Layout: two sections.

TOP SECTION — "Achievability table for 3¢ and 5¢ stamps (n = 1 to 14)":
  - A horizontal strip of 14 labelled cells, each showing an integer 1–14.
  - Cells that ARE achievable: green background (#1a3a2a), green tick (✓) inside.
    Achievable: 3, 5, 6, 8, 9, 10, 11, 12, 13, 14
  - Cells that are NOT achievable: amber background (#3a2a1a), cross (✗) inside.
    Not achievable: 1, 2, 4, 7
  - A vertical red dashed line between cells 7 and 8, labelled "threshold = 7".
  - Below the strip: "Every n ≥ 8 is achievable  (Conjecture 1)"

BOTTOM SECTION — "Why stamps ≠ jugs":
  - Two side-by-side boxes:
      Left box:  "Jugs:   m = 3a + 5b,  a,b ∈ ℤ (any integer)"
      Right box: "Stamps: n = 3a + 5b,  a,b ≥ 0 (non-negative only)"
  - Annotation below right box: "Harder constraint → harder problem"

Footnote: "Figure 1-5 — Stamp achievability table; threshold = 7; Conjecture 1 states all n ≥ 8 work"
""",
    diagram_type="reference",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Non-negativity constraint stated",
            description="Candidate explicitly requires a,b ≥ 0 (not just integers).",
            required=True,
        ),
        DrawingRubricItem(
            label="Table built or threshold identified",
            description="Candidate identifies n=7 as the last non-achievable amount.",
            required=True,
        ),
        DrawingRubricItem(
            label="Conjecture 1 stated",
            description="Candidate states: every n ≥ 8 can be written as 3a+5b with a,b ≥ 0.",
            required=True,
        ),
        DrawingRubricItem(
            label="Jug vs stamp distinction articulated",
            description="Candidate explains why the stamp problem differs from the jug problem.",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must correctly identify the non-negativity constraint, build or "
        "describe the achievability table up to $n = 10$, identify $n = 7$ as the "
        "last failure, and state Conjecture 1."
    ),
    jordan_probes=[
        "What is the fundamental difference between the stamp problem and the jug problem?",
        "Build the achievability table for $n = 1$ to $10$ with 3¢ and 5¢ stamps.",
        "Why is $n = 7$ not achievable? Show this rigorously.",
        "State your conjecture about which amounts are always achievable.",
        "How would the table change if I replaced the 5¢ stamp with a 4¢ stamp?",
        "Does the conjecture change if I use 3¢ and 6¢ stamps? Why?",
    ],
    common_mistakes=[
        "Using negative coefficients — the stamp problem is NOT the jug problem.",
        "Identifying $n = 4$ as the threshold rather than $n = 7$.",
        "Not checking all values up to the claimed threshold before stating the conjecture.",
        "Using 3¢ and 6¢ as if they behave like 3¢ and 5¢ (missing the GCD constraint).",
    ],
    faang_signal=(
        "Candidate immediately notes that with 3¢ and 6¢ stamps only multiples of 3 "
        "are achievable ($\\gcd(3,6) = 3$), and links this back to Bézout — the "
        "non-negativity constraint is what makes the conjecture non-trivial."
    ),
    alex_analogy_seed=(
        "A vending machine that only gives change in 3p and 5p coins. "
        "You can make 8p, 9p, 10p — but can you make 7p? "
        "Build the 'can I make this?' table and look for the pattern."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 6 — Theorem 2: Proving the Threshold for 3 and 5
# ─────────────────────────────────────────────────────────────────────────────

_C6 = Concept(
    id="threshold_proof_3_5",
    name="Proving the Threshold: All $n \\geq 8$ from 3¢ and 5¢",
    order=6,
    book_pages="pp. 12–14",
    core_facts=[
        "Theorem 2: every integer $n \\geq 8$ can be written as $n = 3a + 5b$ for "
        "some non-negative integers $a, b$. Moreover, 8 is best possible.",
        "Proof strategy: show that 8, 9, and 10 are each achievable, then observe that "
        "any $n > 10$ equals $(n-3)$ plus 3, so by induction (or a '+3 step') every "
        "larger integer inherits achievability.",
        "Base cases: $8 = 3 + 5$, $9 = 3 \\times 3$, $10 = 2 \\times 5$.",
        "Inductive step: if $n \\geq 11$, then $n - 3 \\geq 8$. By induction $n - 3 = 3a + 5b$, "
        "so $n = 3(a+1) + 5b$.",
        "Best-possible: $n = 7$ is NOT achievable ($7 = 3a + 5b$ has no non-negative solution), "
        "so the threshold cannot be lowered below 8.",
        "Corollary 1: if $n \\in \\{0, 3, 5, 6\\}$ or $n \\geq 8$, then $n = 3a + 5b$ "
        "with $a, b \\geq 0$. (The full characterisation of achievable amounts.)",
    ],
    why_it_matters=(
        "This is the first time Jordan asks you to prove your conjecture rather than "
        "just state it. The '+3 step' induction is a clean, instructive technique that "
        "generalises directly to the harder theorems. If you can run this proof in "
        "under two minutes, Jordan knows you understand the structure."
    ),
    diagram_prompt=f"""
Generate an SVG proof-flow diagram for Theorem 2.

{SVG_STYLE_GUIDE}

Layout: a vertical proof flowchart.

BOX 1 (top): "Theorem 2: ∀ n ≥ 8,  ∃ a,b ≥ 0:  n = 3a + 5b"

BOX 2: "Base cases"
  Three sub-boxes side by side:
    "8 = 3 + 5"   "9 = 3×3"   "10 = 2×5"
  All three have green borders.

ARROW down labelled "induction on n"

BOX 3: "Inductive step: n ≥ 11"
  Content:
    "n - 3 ≥ 8  →  n - 3 = 3a + 5b  (by IH)"
    "∴  n = 3(a+1) + 5b  ✓"
  Green border.

ARROW down labelled "best-possible argument"

BOX 4: "7 is NOT achievable"
  Content:
    "7 = 3a + 5b,  a,b ≥ 0"
    "Check all cases: a=0→b=7/5 (✗), a=1→b=4/5 (✗), a=2→b=1/5 (✗)"
  Amber border / ✗ icon.

BOX 5 (bottom): "Corollary 1: achievable ⟺  n ∈ {0, 3, 5, 6} or n ≥ 8"

Footnote: "Figure 1-6 — Proof of Theorem 2: base cases + +3 induction; 7 proves best-possible"
""",
    diagram_type="proof_flow",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Theorem statement written",
            description="Candidate states Theorem 2 with the correct bound (n ≥ 8) and non-negativity.",
            required=True,
        ),
        DrawingRubricItem(
            label="Three base cases verified",
            description="Candidate explicitly checks n = 8, 9, 10.",
            required=True,
        ),
        DrawingRubricItem(
            label="Inductive step correct",
            description="Candidate shows n = (n-3) + 3 and applies the induction hypothesis.",
            required=True,
        ),
        DrawingRubricItem(
            label="Best-possible argument",
            description="Candidate proves n=7 is not achievable to show 8 is tight.",
            required=True,
        ),
        DrawingRubricItem(
            label="Corollary stated",
            description="Candidate gives the full characterisation including {0,3,5,6}.",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must write a complete proof: state the theorem, verify the three "
        "base cases, give the inductive step, and prove that $n = 7$ is not achievable. "
        "A proof that omits the best-possible argument is incomplete."
    ),
    jordan_probes=[
        "Prove Theorem 2. You have five minutes — go.",
        "Why do you need three base cases rather than just one?",
        "Prove that $n = 7$ is not achievable — do this rigorously, not by inspection.",
        "What breaks in the proof if I try to prove all $n \\geq 7$ are achievable?",
        "State the full corollary: which amounts are achievable and which are not?",
        "The proof used strong induction implicitly. Point to where.",
    ],
    common_mistakes=[
        "Using only one base case ($n = 8$) and missing that the inductive step jumps by 3, "
        "requiring three base cases to cover all residues mod 3.",
        "Proving $n = 7$ doesn't work by 'checking by hand' without a systematic argument.",
        "Stating the theorem correctly but then proving a weaker version (e.g. all $n \\geq 10$).",
        "Not stating what 'best possible' means — just saying 7 doesn't work without explaining why it matters.",
    ],
    faang_signal=(
        "Candidate immediately identifies that the inductive step uses a '+3 step' "
        "and therefore requires exactly three base cases to cover the residues "
        "$\\{0, 1, 2\\} \\pmod{3}$. Explains this residue structure as the reason "
        "for the shape of the proof before writing a single line."
    ),
    alex_analogy_seed=(
        "A vending machine that dispenses snacks in packs of 3 or 5. "
        "Once you can make 8, 9, and 10 units, you can make any larger amount: "
        "just add another pack of 3 each time. The hard part is bridging the gap up to 8."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 7 — Generalising: Theorem 3 and the General Threshold for 3 and s
# ─────────────────────────────────────────────────────────────────────────────

_C7 = Concept(
    id="generalisation_3_s",
    name="Generalising the Threshold: 3¢ and $s$¢ Stamps",
    order=7,
    book_pages="pp. 14–16",
    core_facts=[
        "Question: if we replace the 5¢ stamp with an $s$¢ stamp ($s$ not a multiple of 3), "
        "what is the smallest $c$ such that every $n \\geq c$ is expressible as $3a + sb$ "
        "with $a, b \\geq 0$?",
        "Conjecture 2: $c = 2(s-1)$.",
        "Theorem 3: if $s$ is not divisible by 3, every $n \\geq 2(s-1)$ can be written "
        "as $n = 3a + sb$ with $a, b \\geq 0$. Moreover $2(s-1)$ is best possible.",
        "Proof strategy (same '+3 step'): show $2s-2$, $2s-1$, and $2s$ are each achievable, "
        "then induct with '+3' steps.",
        "Case $s = 3t+1$: $2s - 2 = 6t = 3 \\times 2t$ ✓. "
        "And $2s - 1 = s + 3t = s + (s-1) = s + 3t$ ✓.",
        "Case $s = 3t+2$: $2s - 2 = s + (s-2) = s + 3t + 2 - 2 = s + 3t$ ✓. "
        "And $2s - 1 = 3(2t+1)$ ✓.",
        "Best-possible: $2s - 3$ is NEVER achievable as $3a + sb$ with $a, b \\geq 0$ "
        "(regardless of $s$, provided $3 \\nmid s$). This requires a separate divisibility argument.",
    ],
    why_it_matters=(
        "This is where the course moves from specific to general. The same proof "
        "technique — anchor three base cases, apply '+3 induction' — works for any "
        "valid $s$. Seeing the abstraction is the key competitive-programming skill: "
        "solve one, then solve the family."
    ),
    diagram_prompt=f"""
Generate an SVG diagram showing the two cases in the Theorem 3 proof.

{SVG_STYLE_GUIDE}

Layout: two columns labelled "Case s = 3t+1" and "Case s = 3t+2".

COLUMN 1 — "s = 3t+1":
  Three stacked sub-boxes:
    "2s = s × 2   ✓"
    "2s-1 = s + 3t   ✓"
    "2s-2 = 3 × 2t   ✓"
  Each box has a green tick.
  Below: "All three base cases covered"

COLUMN 2 — "s = 3t+2":
  Three stacked sub-boxes:
    "2s = 3 × (2t+1) + (2t+2-(2t+1)×... [simplified]   ✓"
    → Use: "2s = 2(3t+2) = 6t+4 = 3(2t+1)+1 — hmm, simplify"
    → Actually: "2s - 1 = 3(2t+1)   ✓"
    → "2s - 2 = s + 3t   ✓"
    → "2s = s × 2   ✓"
  Each box has a green tick.

Centre divider: vertical line.

Below both columns: shared box labelled "Inductive step":
  "If n ≥ 2s-1, then n-3 ≥ 2s-4 ≥ 2(s-1)-2 = 2s-4 ..."
  Simplify: "n - 3 ≥ 2(s-1) → apply induction hypothesis → n = 3(a+1) + sb ✓"

Bottom callout: "2s - 3 is NEVER achievable (best-possible proof by contradiction)"

Footnote: "Figure 1-7 — Theorem 3: two cases give base cases; +3 induction closes the proof"
""",
    diagram_type="proof_flow",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Theorem statement with correct threshold",
            description="Candidate states threshold c = 2(s-1) and non-divisibility hypothesis.",
            required=True,
        ),
        DrawingRubricItem(
            label="Case split identified",
            description="Candidate identifies s = 3t+1 and s = 3t+2 as the two cases.",
            required=True,
        ),
        DrawingRubricItem(
            label="Base cases verified for one case",
            description="Candidate explicitly verifies 2s-2, 2s-1, 2s for at least one case of s.",
            required=True,
        ),
        DrawingRubricItem(
            label="Inductive step outlined",
            description="Candidate explains the +3 inductive step.",
            required=True,
        ),
        DrawingRubricItem(
            label="Best-possible argument for 2s-3",
            description="Candidate argues why 2s-3 is never achievable.",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must state Theorem 3 with the correct threshold $c = 2(s-1)$, "
        "identify the two-case split on $s \\pmod{3}$, verify the base cases for "
        "at least one case, and sketch the inductive step."
    ),
    jordan_probes=[
        "What is the threshold for 3¢ and 7¢ stamps? State and prove Theorem 3 for this case.",
        "Why do we need $s$ to not be a multiple of 3? What happens if $s = 12$?",
        "The proof splits into two cases. What are they, and why exactly two?",
        "Prove that $2s - 3$ is never achievable when $3 \\nmid s$.",
        "For $s = 11$: verify $c = 20$ and show that $n = 19$ is not achievable.",
        "How does Theorem 3 generalise Theorem 2? Make the connection explicit.",
    ],
    common_mistakes=[
        "Forgetting the hypothesis $3 \\nmid s$ — the theorem fails for $s = 6, 9, 12, \\ldots$",
        "Not splitting into the two cases mod 3 — trying to handle $s$ generally without cases.",
        "Claiming the same three base cases as Theorem 2 (8, 9, 10) rather than $2s-2, 2s-1, 2s$.",
        "Not proving the best-possible bound — stating it without justification.",
    ],
    faang_signal=(
        "Candidate recognises immediately that $s \\equiv 0 \\pmod{3}$ forces all "
        "achievable values to be multiples of $\\gcd(3, s) = 3$, and that the theorem "
        "structure (two cases mod 3) echoes the residue argument in Theorem 2. "
        "Articulates the general pattern before writing a single line."
    ),
    alex_analogy_seed=(
        "Replacing the 5¢ stamp with a 7¢ stamp in the post office. The 'no-man's land' "
        "of unachievable amounts grows as $s$ grows — but it always ends at $2(s-1) - 1$. "
        "The proof is the same recipe each time; only the ingredients change."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Concept 8 — The Frobenius / Sylvester Theorem: General Coprime Case
# ─────────────────────────────────────────────────────────────────────────────

_C8 = Concept(
    id="frobenius_theorem",
    name="The Frobenius Coin Problem: General Coprime Case",
    order=8,
    book_pages="pp. 16–18",
    core_facts=[
        "Theorem A (Sylvester–Frobenius): let $r, s$ be positive integers with $\\gcd(r, s) = 1$. "
        "Then every integer $c > (r-1)(s-1)$ can be written as $ar + bs$ with $a, b \\geq 0$. "
        "The bound $(r-1)(s-1)$ is best possible.",
        "The threshold $(r-1)(s-1)$ is called the Frobenius number (or coin problem number) "
        "of $r$ and $s$, sometimes written $g(r, s)$. For $r=3, s=5$: $g(3,5) = (2)(4) = 8 - 1 = 7$ ✓.",
        "Remark B (best-possible): $(r-1)(s-1) - 1$ is NOT achievable as $ar + bs$ "
        "with $a, b \\geq 0$.",
        "Theorem C (symmetry): among the integers $\\{0, 1, \\ldots, (r-1)(s-1) - 1\\}$, "
        "exactly half are expressible in the form $ar + bs$ ($a, b \\geq 0$) and exactly "
        "half are not. This is a beautiful structural symmetry.",
        "Corollary 2: of the $(r-1)(s-1)$ integers in $\\{0, \\ldots, (r-1)(s-1)-1\\}$, "
        "exactly $\\tfrac{(r-1)(s-1)}{2}$ are expressible and $\\tfrac{(r-1)(s-1)}{2}$ are not.",
        "Historical note: this result was proved by James Joseph Sylvester in the 19th century. "
        "The full proof of Theorem A uses Bézout's identity (Theorem 1) and a modular "
        "arithmetic argument to show that the right number of residue classes are covered.",
    ],
    why_it_matters=(
        "This is the theorem that makes the entire chapter cohere. Every specific result "
        "— Theorem 2 for (3, 5), Theorem 3 for (3, s) — is a special case of Theorem A. "
        "Jordan's final ask is always: 'State the general theorem and tell me what "
        "$(r-1)(s-1)$ is computing.' If you can do that, you have demonstrated the "
        "ability to see through specific cases to general structure — which is precisely "
        "what competitive programming and research mathematics require."
    ),
    diagram_prompt=f"""
Generate an SVG diagram illustrating the Frobenius theorem and the symmetry result.

{SVG_STYLE_GUIDE}

Layout: three sections.

TOP SECTION — "Frobenius number formula":
  - A centred display box:
      "g(r, s) = (r-1)(s-1) - 1   [for gcd(r,s) = 1]"
  - Two example rows:
      "g(3, 5) = 2×4 - 1 = 7      ← last non-achievable amount"
      "g(3, 7) = 2×6 - 1 = 11"
  - A small vertical number line from 0 to 12 on the right side:
      Amounts 0,3,5,6,8,9,10,11,12 marked with green ticks.
      Amounts 1,2,4,7 marked with amber crosses.
      Arrow at n=7 labelled "g(3,5) = 7"

MIDDLE SECTION — "Symmetry (Theorem C / Corollary 2)":
  - Title: "Among {{0, 1, ..., (r-1)(s-1)-1}}:"
  - Two side-by-side count boxes:
      Left (green):  "½(r-1)(s-1)   achievable"
      Right (amber): "½(r-1)(s-1)   NOT achievable"
  - For (r,s) = (3,5): "(r-1)(s-1) = 8.  Half = 4 achievable, 4 not achievable."
  - Annotation: "Perfect 50/50 split — a non-obvious structural fact"

BOTTOM SECTION — "Connection to earlier theorems":
  - A small table:
      Theorem 2:  r=3, s=5  →  g=7,  threshold=8=g+1
      Theorem 3:  r=3, s=s  →  g=2(s-1)-1, threshold=2(s-1)
      Theorem A:  general   →  g=(r-1)(s-1)-1

Footnote: "Figure 1-8 — Frobenius number g(r,s) = (r-1)(s-1)-1; Theorem C gives exact 50/50 split below threshold"
""",
    diagram_type="reference",
    solicit_drawing=True,
    drawing_rubric=[
        DrawingRubricItem(
            label="Theorem A stated correctly",
            description="Candidate states: for gcd(r,s)=1, every c > (r-1)(s-1) is expressible; (r-1)(s-1) is best possible.",
            required=True,
        ),
        DrawingRubricItem(
            label="Frobenius number computed for (3,5)",
            description="Candidate computes g(3,5) = 7 and verifies it matches Theorem 2.",
            required=True,
        ),
        DrawingRubricItem(
            label="Symmetry result stated",
            description="Candidate states Theorem C: exactly half of {0,...,(r-1)(s-1)-1} are achievable.",
            required=True,
        ),
        DrawingRubricItem(
            label="Connection to earlier theorems drawn",
            description="Candidate explicitly reduces Theorems 2 and 3 to special cases of Theorem A.",
            required=False,
        ),
        DrawingRubricItem(
            label="Proof sketch or strategy outlined",
            description="Candidate outlines a proof of Theorem A via Bézout and modular arithmetic.",
            required=False,
        ),
    ],
    jordan_minimum_bar=(
        "Candidate must state Theorem A with the correct threshold $(r-1)(s-1)$, "
        "the coprimality hypothesis, and verify it reduces to Theorem 2 for $r=3, s=5$. "
        "Must state Corollary 2 (the 50/50 symmetry). Best-possible argument is required."
    ),
    jordan_probes=[
        "State the Frobenius / Sylvester theorem in full generality.",
        "Compute $g(4, 11)$ — what is the largest amount NOT expressible as $4a + 11b$ with $a,b \\geq 0$?",
        "Verify that $g(3, 5) = 7$ is consistent with Theorem 2.",
        "State and explain the symmetry result (Theorem C). Why is the 50/50 split surprising?",
        "What is the Frobenius number for $(r, s) = (2, 2k+1)$? Compute it and prove it.",
        "Sketch the proof of Theorem A — which lemmas do you need and in what order?",
        "What goes wrong if $\\gcd(r, s) = 2$?",
    ],
    common_mistakes=[
        "Writing the Frobenius number as $(r-1)(s-1)$ rather than $(r-1)(s-1) - 1$.",
        "Not knowing the symmetry result (Theorem C) — candidates often only know the threshold.",
        "Forgetting the coprimality hypothesis — the theorem is false without it.",
        "Not being able to connect $g(3, 5) = 7$ back to Theorem 2.",
        "Confusing 'the threshold' ($(r-1)(s-1)$, the first always-achievable value) with "
        "'the Frobenius number' ($(r-1)(s-1) - 1$, the last non-achievable value).",
    ],
    faang_signal=(
        "Candidate states both the threshold formula and the symmetry corollary "
        "without prompting, computes $g(r, s) = rs - r - s$ as the equivalent form "
        "(since $(r-1)(s-1) - 1 = rs - r - s$), and remarks that Sylvester proved "
        "this in the 19th century — grounding the result historically. "
        "Bonus: knows there is no closed-form generalisation to three stamp denominations."
    ),
    alex_analogy_seed=(
        "A currency system with only two coin denominations. The Frobenius number "
        "tells you the largest amount you literally cannot pay exactly — after that, "
        "every amount is fine. And exactly half the amounts below the threshold "
        "are payable: a perfect, unexpected symmetry hidden in the problem."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Exported curriculum
# ─────────────────────────────────────────────────────────────────────────────

CHAPTER_1_CONCEPTS: list[Concept] = [
    _C1,  # Problem-Solving Framework
    _C2,  # The Jug Problem
    _C3,  # Bézout's Identity
    _C4,  # Consecutive Numbers Problem
    _C5,  # Stamp Problem: Discovery
    _C6,  # Theorem 2: Proving the 3 & 5 Threshold
    _C7,  # Generalising: Theorem 3 (3 and s)
    _C8,  # Frobenius / Sylvester Theorem (General)
]

# Lookup by id
CONCEPT_BY_ID: dict[str, Concept] = {c.id: c for c in CHAPTER_1_CONCEPTS}

# Concepts that require candidate proofs or sketches — activates the proof-input UI
DRAWING_CONCEPTS: list[Concept] = [c for c in CHAPTER_1_CONCEPTS if c.solicit_drawing]

# Ordered concept ids — used by teach sequencer
CONCEPT_ORDER: list[str] = [c.id for c in CHAPTER_1_CONCEPTS]
