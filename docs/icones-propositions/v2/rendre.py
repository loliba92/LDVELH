"""Planche de comparaison : python rendre.py sortie.png"""
import pathlib, sys
from playwright.sync_api import sync_playwright
fs = sorted(pathlib.Path(".").glob("[0-9]-*.svg"))
cards = "".join(f'<div class="c"><h3>{f.stem}</h3><div class="grand">'+f.read_text(encoding="utf-8")+"</div></div>" for f in fs)
html = f'<html><body style="margin:0;background:#f0e8d6;font-family:system-ui"><style>.w{{display:grid;grid-template-columns:repeat({len(fs)},1fr);gap:16px;padding:20px;width:{len(fs)*380}px}}.c{{background:#fbf7ec;border:1px solid #d9ccb2;border-radius:8px;padding:12px}}h3{{margin:0 0 8px;font-size:15px}}.grand svg{{width:340px;height:340px;display:block}}</style><div class="w">{cards}</div></body></html>'
pathlib.Path("/tmp/_pl.html").write_text(html, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"); pg = b.new_page(viewport={"width": len(fs)*380+40, "height": 460})
    pg.goto("file:///tmp/_pl.html"); pg.wait_for_timeout(300); pg.screenshot(path=sys.argv[1], full_page=True)
