"""Propositions d'icône v3 : mage ancien, style gravure. python generer.py"""
G, B, N = "#d9b45f", "#2a1c13", "#14100b"
def base(inner):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><radialGradient id="h"><stop offset="0" stop-color="{G}" stop-opacity=".3"/><stop offset="1" stop-color="{G}" stop-opacity="0"/></radialGradient><clipPath id="c"><circle cx="32" cy="32" r="29.4"/></clipPath></defs><circle cx="32" cy="32" r="30" fill="{B}"/><g clip-path="url(#c)"><circle cx="32" cy="34" r="24" fill="url(#h)"/>{inner}</g><circle cx="32" cy="32" r="26.5" fill="none" stroke="{G}" stroke-width="1.6"/></svg>'''

def visage(cheveux=True):
    """Tête de face : visage, cheveux longs, barbe en mèches (centrée en x = 32, haut du front y = 30)."""
    cheveux_p = f'<path d="M21.5 31C19.5 41 20.5 51 24.6 58.5L28.6 54L31 60.5L33 54.6L35.8 60L39.4 54C42.6 50 44.4 41 42.6 31C37.6 34.4 26.6 34.4 21.5 31Z" fill="{G}"/>' if cheveux else \
        f'<path d="M24 31C23.4 40 24.6 50 28.6 58.5L31 54L32 60.5L33 54L35.4 58.5C39.4 50 40.6 40 40 31C36 33.6 28 33.6 24 31Z" fill="{G}"/>'
    return f'''{cheveux_p}
<path d="M24.4 33.4C23.4 37.6 24.2 41 26.8 43M39.8 33.4C40.8 37.6 40 41 37.4 43" fill="none" stroke="{B}" stroke-width="1.1" stroke-linecap="round"/>
<path d="M24.8 34.6L30.8 36.6M39.2 34.6L33.2 36.6" stroke="{B}" stroke-width="2.4" stroke-linecap="round"/>
<ellipse cx="28.2" cy="38.2" rx="1.7" ry=".75" fill="{B}"/><ellipse cx="35.8" cy="38.2" rx="1.7" ry=".75" fill="{B}"/>
<path d="M32.2 37.6L31.2 42.2Q32.4 43.4 34.2 42.2" fill="none" stroke="{B}" stroke-width="1.15" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M32 44C28.8 42.8 25.6 44.2 24.2 46.8M32 44C35.2 42.8 38.4 44.2 39.8 46.8" fill="none" stroke="{B}" stroke-width="1.3" stroke-linecap="round"/>
<path d="M32 46.8V57M28 47.4C28 51.4 28.8 54.8 30 57.6M36 47.4C36 51.4 35.2 54.8 34 57.6M24.4 42.4C24.4 47 25.6 52 27.4 56M39.8 42.4C39.8 47 38.6 52 36.8 56" fill="none" stroke="{B}" stroke-width=".9" stroke-linecap="round" opacity=".8"/>'''

# B2. Le mage au chapeau, visage plus large
b2 = base(f'''
<g transform="translate(32 36) scale(1.14) translate(-32 -36)">{visage(True)}</g>
<ellipse cx="32" cy="29.6" rx="19.5" ry="4" fill="{N}" stroke="{G}" stroke-width="1.3"/>
<path d="M20.5 28C21.6 21 25.4 14.4 31.6 9.8C36.4 6.6 43.4 7.8 45.6 13C41.2 11.4 37.4 13.6 36.4 17.4C35.4 21.4 37 25 43.6 28.2C36.4 27.2 28 27.2 20.5 28Z" fill="{N}" stroke="{G}" stroke-width="1.3" stroke-linejoin="round"/>
<path d="M21.6 24.8C28 23.8 36.8 24 42 25.4" fill="none" stroke="{G}" stroke-width="1.2"/>
''')


def mage(fond=B, anneau2=False, braise=False, etoile=False):
    """Le mage au chapeau, avec quelques variantes."""
    svg = base(f'''
<g transform="translate(32 36) scale(1.14) translate(-32 -36)">{visage(True)}</g>
{"<g>" + "".join(f'<circle cx="{x}" cy="38.4" r="3.4" fill="url(#l)"/><circle cx="{x}" cy="38.4" r="1" fill="#d4332f"/>' for x in (27.6, 36.4)) + "</g>" if braise else ""}
<ellipse cx="32" cy="29.6" rx="19.5" ry="4" fill="{N}" stroke="{G}" stroke-width="1.3"/>
<path d="M20.5 28C21.6 21 25.4 14.4 31.6 9.8C36.4 6.6 43.4 7.8 45.6 13C41.2 11.4 37.4 13.6 36.4 17.4C35.4 21.4 37 25 43.6 28.2C36.4 27.2 28 27.2 20.5 28Z" fill="{N}" stroke="{G}" stroke-width="1.3" stroke-linejoin="round"/>
<path d="M21.6 24.8C28 23.8 36.8 24 42 25.4" fill="none" stroke="{G}" stroke-width="1.2"/>
{etoile_(31.2, 18.4, 2.4) if etoile else ""}
''')
    svg = svg.replace(f'<circle cx="32" cy="32" r="30" fill="{B}"/>', f'<circle cx="32" cy="32" r="30" fill="{fond}"/>')
    if braise:
        svg = svg.replace("<defs>", '<defs><radialGradient id="l"><stop offset="0" stop-color="#d4332f" stop-opacity=".85"/><stop offset="1" stop-color="#d4332f" stop-opacity="0"/></radialGradient>', 1)
    if anneau2:
        svg = svg.replace('</svg>', f'<circle cx="32" cy="32" r="29" fill="none" stroke="{G}" stroke-width=".6" opacity=".7"/></svg>')
    return svg
def etoile_(cx, cy, r):
    return f'<path d="M{cx} {cy-r}L{cx+r*.3} {cy-r*.3}L{cx+r} {cy}L{cx+r*.3} {cy+r*.3}L{cx} {cy+r}L{cx-r*.3} {cy+r*.3}L{cx-r} {cy}L{cx-r*.3} {cy-r*.3}Z" fill="{G}"/>'

for n, s in (("1-mage-sobre", mage()), ("2-mage-regard-de-braise", mage(braise=True)), ("3-mage-fond-noir", mage(fond="#120c08", anneau2=True, etoile=True))):
    open(f"{n}.svg", "w", encoding="utf-8").write(s)
