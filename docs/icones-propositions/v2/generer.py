"""Génère les propositions d'icône « adulte » (v2) : python generer.py"""
G, B, N, R = "#d9b45f", "#2a1c13", "#120c08", "#d4332f"   # or, brun, noir chaud, rouge braise
def base(inner):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><radialGradient id="l"><stop offset="0" stop-color="{R}" stop-opacity=".9"/><stop offset="1" stop-color="{R}" stop-opacity="0"/></radialGradient></defs><circle cx="32" cy="32" r="30" fill="{B}"/><clipPath id="c"><circle cx="32" cy="32" r="29.4"/></clipPath><g clip-path="url(#c)">{inner}</g><circle cx="32" cy="32" r="26.5" fill="none" stroke="{G}" stroke-width="1.6"/></svg>'''
def oeil(x, y, r=1.6):
    return f'<circle cx="{x}" cy="{y}" r="{r*2.6}" fill="url(#l)"/><circle cx="{x}" cy="{y}" r="{r}" fill="{R}"/>'

# 1. Le nécromancien : capuche sombre, visage de mort, regard de braise
p1 = base(f'''
<path d="M32 7.5C21 9.5 15 19.5 15 30.5C15 37.5 17.5 43 20.5 47.5L17.5 53.5C25 56.5 39 56.5 46.5 53.5L43.5 47.5C46.5 43 49 37.5 49 30.5C49 19.5 43 9.5 32 7.5Z" fill="{N}" stroke="{G}" stroke-width="1.5" stroke-linejoin="round"/>
<path d="M22 49.5C27 52 37 52 42 49.5M26 52.5V55M32 53V55.6M38 52.5V55" fill="none" stroke="{G}" stroke-width="1" stroke-linecap="round" opacity=".7"/>
<path d="M32 15.5C25.5 15.5 22.3 20.5 22.3 26C22.3 30 24 32.5 26 34V40.5C26 42.3 27.4 43.5 29 43.5H35C36.6 43.5 38 42.3 38 40.5V34C40 32.5 41.7 30 41.7 26C41.7 20.5 38.5 15.5 32 15.5Z" fill="{G}"/>
<path d="M24.2 24.8L30.2 27.4L29.4 31.6L24.6 30Z" fill="{N}"/><path d="M39.8 24.8L33.8 27.4L34.6 31.6L39.4 30Z" fill="{N}"/>
{oeil(28.2,28.6,1.1)}{oeil(35.8,28.6,1.1)}
<path d="M32 31.5L30.4 35.2H33.6Z" fill="{N}"/>
<path d="M28.5 38V43M31 38V43.4M33 38V43.4M35.5 38V43" stroke="{N}" stroke-width="1" stroke-linecap="round"/>
<path d="M26.4 37.5H37.6" stroke="{N}" stroke-width="1"/>
''')

# 2. La liche : tête de mort coiffée d'un chapeau de mage
p2 = base(f'''
<path d="M23 25C24.5 18 28 12 33.5 6.8C35.6 5.6 38.4 7 37.6 9.6C36.8 11.4 36 12.6 36.8 14.6C38.6 19 40.4 22 41.6 25Z" fill="{G}"/>
<path d="M23.4 21.6C28 23 37 23 41 21.6" fill="none" stroke="{N}" stroke-width="2"/>
<path d="M25.6 31.5C25.6 26.5 28.4 24 32 24C35.6 24 38.4 26.5 38.4 31.5C38.4 34 37.2 36 35.8 37.2V42.4C35.8 44 34.6 45 33.2 45H30.8C29.4 45 28.2 44 28.2 42.4V37.2C26.8 36 25.6 34 25.6 31.5Z" fill="{G}"/>
<ellipse cx="32" cy="25.5" rx="15.5" ry="3.2" fill="{G}"/>
<path d="M26.4 30.4L31 32.2L30.4 35.2L26.8 34Z" fill="{N}"/><path d="M37.6 30.4L33 32.2L33.6 35.2L37.2 34Z" fill="{N}"/>
{oeil(29,32.7,0.95)}{oeil(35,32.7,0.95)}
<path d="M32 35L31 37.4H33Z" fill="{N}"/>
<path d="M29.8 40.2V44.6M32 40V44.8M34.2 40.2V44.6M28.4 40.2H35.6" stroke="{N}" stroke-width=".9" stroke-linecap="round"/>
<path d="M21.5 50.5C27 47.8 37 47.8 42.5 50.5L45 55.5C37 58 27 58 19 55.5Z" fill="{N}" stroke="{G}" stroke-width="1.2" stroke-linejoin="round"/>
<path d="M32 49.2V57" stroke="{G}" stroke-width=".9" opacity=".7"/>
''')

# 3. Le sorcier maléfique : visage dans l'ombre du chapeau, regard de braise, barbe en pointes
p3 = base(f'''
<path d="M22.6 29C24.4 21 27.4 14 32.6 7.6C34.8 6.2 38 7.6 37.2 10.2C36.4 12 35.8 13.2 36.6 15C38.4 19.8 40.4 24.4 42 29Z" fill="{G}"/>
<path d="M23 25.2C28 27 37.4 27 42 25.2" fill="none" stroke="{N}" stroke-width="2"/>
<ellipse cx="32.5" cy="29.6" rx="16" ry="3.4" fill="{G}"/>
<path d="M23.2 31.4C24.4 37 28 40.4 32.5 40.6C37 40.4 40.6 37 41.8 31.4C38 33.6 27 33.6 23.2 31.4Z" fill="{N}"/>
<path d="M26 32.4L30.4 34.4M39 32.4L34.6 34.4" stroke="{G}" stroke-width="1.1" stroke-linecap="round"/>
{oeil(28.4,35,1.1)}{oeil(36.6,35,1.1)}
<path d="M32.5 33.6V38.4" stroke="{G}" stroke-width="1" stroke-linecap="round"/>
<path d="M22.8 36C22.4 43 24.4 50 28.2 56.4L30.8 51.6L32.5 57.6L34.2 51.6L36.8 56.4C40.6 50 42.6 43 42.2 36C40.6 39.4 37 41.4 32.5 41.4C28 41.4 24.4 39.4 22.8 36Z" fill="{G}"/>
<path d="M29.4 43.4Q32.5 45 35.6 43.4" fill="none" stroke="{N}" stroke-width="1.1" stroke-linecap="round"/>
<path d="M27 47C28 51 29 54 30 56M38 47C37 51 36 54 35 56" fill="none" stroke="{N}" stroke-width=".8" opacity=".6"/>
''')
for n, s in (("1-necromancien", p1), ("2-liche-au-chapeau", p2), ("3-sorcier-malefique", p3)):
    open(f"{n}.svg", "w", encoding="utf-8").write(s)
