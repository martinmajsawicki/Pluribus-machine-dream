# PLUR1BUS Machine Dream

AI-assisted analysis of Pluribus Season 1. Three models decode the show through five analytical lenses — narrative, character, theme, visual language, ideology. Human gathers, AI synthesizes, human curates.

🔗 **[View the Website](https://martinmajsawicki.github.io/Pluribus-machine-dream/)**

---

## The Approach

1. **Gather** — AI searched for quality materials. Human gathered additional sources: creator interviews, episode descriptions, critical analysis, cast commentary. Human oversight throughout.

2. **Compile** — AI curated the research into a structured dossier — distilling a mountain of text into focused context. Human reviewed and refined.

3. **Decode** — Three AI models analyzed through 5 lenses:
   - Narrative Mechanics
   - Character Functions
   - Thematic Decoding
   - Visual & Symbolic Language
   - Ideological Reading

4. **Curate** — Human reads the 15 reports. Selects the sharpest insights. AI finds patterns; human decides what matters.

---

## Why This Works

**AI excels at:** Pattern recognition, synthesizing large amounts of information, finding connections across sources, systematic analysis through defined frameworks.

**AI struggles with:** Subtext and implication, symbolic meaning that isn't stated, emotional resonance, the "unsaid" in storytelling, original creative vision.

So instead of asking AI to generate (what it's bad at), ask it to decode and analyze (what it's good at). Use that foundation for everything else.

---

## Sample Discoveries

> "The reversal from countdown to count-up signifies a civilization that has solved desire and halted becoming. By the finale, the clock measures not history, but Carol's remaining freedom." — *GPT*

> "The betrayal is not that Zosia lied, but that love was instrumentalized toward a collective goal. The show never denies the love was real—only that it was allowed to be singular." — *GPT*

> "'Pluribus' names what has been lost, not what remains. The many no longer exist, making the title an elegy disguised as a name." — *Claude*

> "The Others will starve rather than kill; Carol will nuke rather than submit." — *Gemini*

---

## Repository Structure

```
├── index.html                    # Website
├── METHODOLOGY.md                # How this approach works (and its limits)
├── PLURIBUS_YELLOW_BANNER.png    # Hero image
├── pluribus_decode.py            # CLI for running the experiment
│
├── prompts/
│   ├── SEASON_1_DOSSIER.md       # Context document (~18,500 chars)
│   ├── rewrite_brief_prompt.md   # Curation prompt
│   └── phase_1_decoding/
│       ├── 1_narrative_mechanics.md
│       ├── 2_character_functions.md
│       ├── 3_thematic_decoding.md
│       ├── 4_visual_symbolic.md
│       └── 5_ideological_reading.md
│
├── results/
│   ├── phase_1_decoding/         # 15 AI reports (5 BRIEF files selected)
│   └── synthesis/
│       ├── meta_brief.md         # Best quotes curated
│       └── rewritten/            # Model curation outputs
│
└── sources/                      # Gathered research materials
    ├── gilligan_interviews.md    # Creator interviews
    ├── seehorn_interviews.md     # Cast interviews
    ├── symbolism_analysis.md     # Visual/thematic analysis
    └── ...                       # 10 research files total
```

---

## Models Used

| Model | Strength |
|-------|----------|
| **GPT-5.2** | Tight, punchy analysis. Strong on structure and mechanics. |
| **Claude Opus 4.5** | Rich, deep analysis. Strong on character psychology. |
| **Gemini 3 Pro** | Unique finds. Strong on ideology and cultural context. |

All models accessed via [OpenRouter](https://openrouter.ai/).

---

## About Pluribus

*Pluribus* (stylized as **PLUR1BUS**) is a post-apocalyptic science fiction series created by Vince Gilligan for Apple TV+, premiered November 2025.

A signal from space transforms humanity into a peaceful collective consciousness. Thirteen people are immune. Season 1 ends with Carol Sturka standing next to an atom bomb — a gift from the Others who cannot refuse her anything.

---

## Credits

Created by **Marcin Sawicki** with **Claude Code**, December 2025.

*Pluribus is property of Vince Gilligan / Apple TV+ / Sony Pictures Television. This project is for educational purposes.*
