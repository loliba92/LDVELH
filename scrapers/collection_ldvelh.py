"""Extrait le catalogue et les prix de collection-ldvelh.fr pour les 5 versions (univers V1 à V5).

Le site est « calé » sur la version 1 ; le menu « Changer d'Univers » bascule vers /version/V2, etc.
Le choix est mémorisé par la session : on utilise donc une session par version.

    python scrapers/collection_ldvelh.py
"""
import csv
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://www.collection-ldvelh.fr'
VERSIONS = ['V1', 'V2', 'V3', 'V4', 'V5']  # « univers » du site (menu « Changer d'Univers »)
PAUSE = 1.0  # secondes entre deux requêtes, pour ne pas surcharger le site
HEADERS = {'User-Agent': 'LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux)'}

# Liste des numéros de livres possédés (version 1 uniquement), avec doublons possibles
owned_book_numbers = [
    # --- 200 ---
    '252', '268', '270', '271', '285', '288', '289', '290', '291', '293',
    '294', '295', '296', '297', '298',
    # --- 300 ---
    '310', '311', '314', '316', '317', '318', '319', '320', '321', '323',
    '324', '325', '327', '329', '330', '331', '332', '333', '334', '335',
    '337', '338', '339', '341', '342', '353', '354', '356', '362', '363',
    '364', '365', '368', '369', '370', '371', '372', '373', '383', '384',
    '385', '390',
    # --- 400 ---
    '401', '402', '403', '404', '405', '408', '409', '414', '415', '416',
    '422', '423', '424', '427', '470', '471', '473', '485', '487',
    # --- 500 ---
    '502', '503', '504', '505', '506', '512', '522', '527', '528', '529',
    '530', '539', '540', '550', '570', '571', '574', '575', '592', '593',
    '594',
    # --- 600 ---
    '608', '611', '612', '620', '621', '623', '631', '643', '662', '671',
    '679', '681', '698', '699',
    # --- 700 ---
    '706', '749']
owned_count = Counter(owned_book_numbers)

# Livres hors système du site, ajoutés à la main (version 1)
nouveaux_livres = [
    {'titre': "L'Aventurie", 'prix': 15, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "001", 'own': 2, 'date': None},
    {'titre': "Le Livre des Règles", 'prix': 15, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "002", 'own': 2, 'date': None},
    {'titre': "Le Livre des Règles 2", 'prix': 15, 'serie': "L'Œil Noir ", 'note': "5", 'numero': "003", 'own': 2, 'date': None},
    {'titre': 'Le Livre des Aventures', 'prix': 15, 'serie': "L'Œil Noir    ", 'note': "5", 'numero': "004", 'own': 2, 'date': None},
    {'titre': 'Héros, Monstres et Forces Obscures', 'prix': 20, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "005", 'own': 1, 'date': None},
]

FIELDNAMES = ['version', 'titre', 'prix', 'serie', 'rang_serie', 'note', 'numero', 'own', 'date', 'isbn',
              'last_date', 'link', 'collection_percentage', 'prix_convenable', 'prix_bon_etat',
              'prix_tres_bon_etat']


def get(session, url):
    time.sleep(PAUSE)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response


def choisir_version(session, version):
    """Bascule la session sur l'univers demandé et vérifie que le site l'a bien pris en compte."""
    get(session, f'{BASE_URL}/version/{version}')
    page = BeautifulSoup(get(session, f'{BASE_URL}/books').content, 'html.parser')
    entete = page.find('p', class_='header-font')
    if entete is None or entete.text.strip() != f'Univers Version {version[1:]}':
        raise RuntimeError(f"Le site n'a pas basculé sur {version} (en-tête : "
                           f"{entete.text.strip() if entete else 'absent'})")
    return page


def get_prices_by_condition_bundle(session):
    soup = BeautifulSoup(get(session, f'{BASE_URL}/stats/bundle').content, 'html.parser')
    prices_by_book = {}
    for book_element in soup.find_all('input', {'class': 'livre-input'}):
        title = book_element.find_parent().text.strip()
        prices_by_book[title] = {
            'prix_convenable': book_element['data-price'],
            'prix_bon_etat': book_element['data-beprice'],
            'prix_tres_bon_etat': book_element['data-tbeprice'],
        }
    return prices_by_book


def get_collection_percentages(session):
    soup = BeautifulSoup(get(session, f'{BASE_URL}/stats').content, 'html.parser')
    percentages = {}
    for li in soup.find_all('li', class_='d-flex space-between w-100'):
        titre = li.find('a', class_='dark-grey').text.strip()
        percentages[titre] = li.find('span', class_='col-xs-2 small p-0 right').text.strip().replace('%', '')
    return percentages


def scrape_version(version, current_date):
    session = requests.Session()
    session.headers.update(HEADERS)
    page = choisir_version(session, version)
    prices_by_condition = get_prices_by_condition_bundle(session)
    percentages = get_collection_percentages(session)

    livres = []
    for book in page.find_all('div', {'data-titre': True}):
        lien = book.find('a', href=True)
        href = lien['href'] if lien else None
        serie_brute = book.get('data-serie', '')
        serie, _, rang = serie_brute.partition('-')  # « Défis Fantastiques-01 » : série et rang dans la série
        titre = book['data-titre']
        info = {
            'version': version,
            'titre': titre,
            'prix': book['data-prix'],
            'serie': serie.strip() or None,
            'rang_serie': rang.strip() or None,
            'note': book['data-note'],
            'numero': book['data-numero'],
            'own': owned_count[book['data-numero']] if version == 'V1' else 0,
            'date': book['data-date'],
            'isbn': href.split('/')[-1] if href else None,
            'last_date': current_date,
            'link': href,
            'collection_percentage': percentages.get(titre, 'N/A'),
        }
        info.update(prices_by_condition.get(titre, {'prix_convenable': None, 'prix_bon_etat': None,
                                                    'prix_tres_bon_etat': None}))
        livres.append(info)
    print(f'  {version} : {len(livres)} livres')
    return livres


def main():
    current_date = datetime.now().strftime("%Y-%m-%d")
    books_data = []
    for version in VERSIONS:
        books_data += scrape_version(version, current_date)
    for livre in nouveaux_livres:
        books_data.append({**livre, 'version': 'V1', 'last_date': current_date})

    output_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw' / 'collection-ldvelh'
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f'books_data-{current_date}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(books_data)
    print(f"{len(books_data)} lignes exportées avec succès dans {filename}")


if __name__ == '__main__':
    main()
