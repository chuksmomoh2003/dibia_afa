from __future__ import annotations

from difflib import get_close_matches
from pathlib import Path
import html
import re
import unicodedata

import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "afa_lookup_data.csv"
MAX_COMBINATIONS = 3


def normalize_text(value: str) -> str:
    """Normalize spacing, punctuation and letter case without reversing word order."""
    value = unicodedata.normalize("NFKC", str(value))
    value = (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9'\s-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_entries(raw_value: str) -> list[str]:
    """Split comma- or line-separated combinations and remove empty entries."""
    parts = re.split(r"[,\n]+", raw_value)
    return [part.strip() for part in parts if part.strip()]


@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Lookup dataset not found: {DATA_FILE}")

    return pd.read_csv(DATA_FILE).fillna("")


def build_lookup(data: pd.DataFrame) -> dict[str, dict]:
    lookup: dict[str, dict] = {}

    for _, row in data.iterrows():
        candidates = [row["exact_combination"]]
        candidates.extend(
            alias.strip()
            for alias in str(row["aliases"]).split(";")
            if alias.strip()
        )

        for candidate in candidates:
            key = normalize_text(candidate)
            if key:
                lookup[key] = row.to_dict()

    return lookup


def render_result(number: int, result: dict) -> None:
    combination = html.escape(str(result["exact_combination"]))
    igbo = html.escape(str(result["igbo_meanings"]))
    english = html.escape(str(result["english_meanings"]))

    st.markdown(
        f"""
        <div class="result-card">
            <div class="result-number">Lookup {number}</div>
            <div class="combination">{combination}</div>
            <div class="language-label">Igbo</div>
            <div class="meaning">{igbo}</div>
            <div class="language-label english-label">English</div>
            <div class="meaning">{english}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_not_found(number: int, query: str, suggestions: list[str]) -> None:
    st.error(f'Lookup {number}: No exact match was found for "{query}".')
    st.caption(
        "Check the spelling and word order. The app does not reverse combinations."
    )

    if suggestions:
        st.write("Possible stored combinations:")
        for suggestion in suggestions:
            st.write(f"• {suggestion}")


st.set_page_config(
    page_title="Afa Meaning Lookup",
    page_icon="🔎",
    layout="centered",
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 900px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .subtitle {
            font-size: 1.05rem;
            color: #555;
            margin-bottom: 1.5rem;
        }

        .result-card {
            border: 1px solid rgba(128, 128, 128, 0.30);
            border-radius: 14px;
            padding: 1.25rem 1.35rem;
            margin: 1rem 0;
            background: rgba(128, 128, 128, 0.06);
        }

        .result-number {
            font-size: 0.80rem;
            text-transform: uppercase;
            letter-spacing: 0.08rem;
            opacity: 0.65;
            margin-bottom: 0.25rem;
        }

        .combination {
            font-size: 1.65rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }

        .language-label {
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06rem;
            opacity: 0.68;
        }

        .english-label {
            margin-top: 0.9rem;
        }

        .meaning {
            font-size: 1.05rem;
            line-height: 1.55;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Afa Meaning Lookup")
st.markdown(
    '<div class="subtitle">Enter up to three Afa combinations in one box, '
    "separated by commas. The app returns their stored Igbo and English "
    "meanings in the same order.</div>",
    unsafe_allow_html=True,
)

try:
    data = load_data()
except Exception as exc:
    st.error(f"Could not load the Afa lookup dataset: {exc}")
    st.stop()

lookup = build_lookup(data)
all_alias_keys = list(lookup.keys())

with st.form("lookup_form"):
    raw_entries = st.text_input(
        "Afa combinations",
        placeholder="Example: agali aka, agali ogoli, ogoli aka",
        help="Enter one, two or three complete combinations separated by commas.",
    )

    submitted = st.form_submit_button(
        "Extract meanings",
        type="primary",
        use_container_width=True,
    )

if submitted:
    entries = parse_entries(raw_entries)

    if not entries:
        st.warning("Enter at least one Afa combination.")
    elif len(entries) > MAX_COMBINATIONS:
        st.warning(
            f"Enter no more than {MAX_COMBINATIONS} combinations. "
            f"You entered {len(entries)}."
        )
    else:
        st.divider()
        st.subheader("Meanings")

        for number, query in enumerate(entries, start=1):
            normalized_query = normalize_text(query)
            result = lookup.get(normalized_query)

            if result:
                render_result(number, result)
            else:
                close_keys = get_close_matches(
                    normalized_query,
                    all_alias_keys,
                    n=3,
                    cutoff=0.68,
                )

                suggestions: list[str] = []
                seen: set[str] = set()

                for key in close_keys:
                    stored_name = str(lookup[key]["exact_combination"])
                    if stored_name not in seen:
                        suggestions.append(stored_name)
                        seen.add(stored_name)

                render_not_found(number, query, suggestions)

with st.expander("How to use this app"):
    st.write(
        """
        1. Type one, two or three complete Afa combinations in the search box.
        2. Separate the combinations with commas.
        3. Example: `agali aka, agali ogoli, ogoli aka`
        4. Click **Extract meanings**.
        5. The app displays the stored Igbo and English meanings in the entered order.
        6. Word order is respected. A reversed combination is not substituted.
        """
    )

st.caption(
    f"Local index: {len(data)} ordered Afa combinations. "
    "Only combination, Igbo meaning and English meaning are displayed."
)
