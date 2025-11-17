def theme_css() -> str:
    """
    Returns a <style> block that:
      - Defines light and dark color tokens with CSS variables.
      - Applies to Streamlit's main area and sidebar via stable `data-testid` hooks.
      - Always follows system color scheme (prefers-color-scheme).
      - Hides Streamlit header and footer.
      - Styles segmented control with custom color.
      - Keeps sidebar visible and interactive.
    """
    return """
<style>
:root {
  --bg: #ffffff;
  --bg-alt: #f6f7fb;
  --fg: #111111;
  --muted: #475569;
  --primary: #3b82f6;
  --border: #e5e7eb;
  --segmented-active: #A62639;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #271D06;
    --bg-alt: #1E1504;
    --fg: #E6E9EF;
    --muted: #a0a3ad;
    --primary: #FFD700;
    --border: #5C3B00;
    --segmented-active: #A62639;
  }
}

@media (prefers-color-scheme: light) {
  :root {
    --bg: #FFF2D6;
    --bg-alt: #F5E6C2;
    --fg: #111111;
    --muted: #475569;
    --primary: #3b82f6;
    --border: #e5e7eb;
    --segmented-active: #A62639;
  }
}

/* Hide Streamlit header and footer */
[data-testid="stHeader"] {
  background-color: transparent !important;
  box-shadow: none !important;
  border-bottom: none !important;
}
footer {
  visibility: hidden;
}

/* Smooth transitions */
@media (prefers-reduced-motion: no-preference) {
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"] {
    transition: background-color .2s ease, color .2s ease, border-color .2s ease;
  }
}

/* Main content area */
[data-testid="stAppViewContainer"],
.block-container {
  background-color: var(--bg);
  color: var(--fg);
}

a, .stMarkdown a {
  color: var(--primary);
}

div[data-baseweb="input"] input,
textarea, .stTextInput input, .stNumberInput input, .stTextArea textarea,
.stSelectbox div[role="combobox"], .stMultiSelect div[role="combobox"] {
  background-color: var(--bg-alt) !important;
  color: var(--fg) !important;
  border: 1px solid var(--border) !important;
}

.stButton > button, .stDownloadButton > button {
  background-color: #D5AC4E !important;
  color: #111111 !important;
  border: 1px solid #b88f3f !important;
  border-radius: 5px;
  font-weight: bold;
}

.stButton > button:hover,
[data-testid="stSidebar"] .stButton > button:hover {
  background-color: #c49b3f !important;
  border-color: #a87f2e !important;
}

hr {
  border-color: var(--border);
}

/* Sidebar styling */
[data-testid="stSidebar"] {
  background-color: var(--bg-alt);
  border-right: 1px solid var(--border);
  color: var(--fg);
}

[data-testid="stSidebar"] * {
  color: var(--fg) !important;
}

[data-testid="stSidebar"] a {
  color: var(--primary) !important;
}

[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] .stSelectbox div[role="combobox"],
[data-testid="stSidebar"] .stMultiSelect div[role="combobox"],
[data-testid="stSidebar"] .stNumberInput input {
  background-color: var(--bg) !important;
  color: var(--fg) !important;
  border: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stDownloadButton > button {
  background-color: #D5AC4E !important;
  color: #111111 !important;
  border: 1px solid #b88f3f !important;
  border-radius: 5px;
  font-weight: bold;
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  color: var(--fg) !important;
}

[data-testid="stSidebar"] .stRadio [role="radiogroup"] > div[aria-checked="true"] label span {
  font-weight: 600;
}

/* Segmented control styling */
[data-testid="stSegmentedControl"] [aria-checked="true"] {
  background-color: var(--segmented-active) !important;
  color: #ffffff !important;
  font-weight: bold;
}
</style>
"""
