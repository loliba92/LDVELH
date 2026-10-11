import requests
from bs4 import BeautifulSoup
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter


def get_prices_by_condition_bundle():
    url = 'https://www.collection-ldvelh.fr/stats/bundle'
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    prices_by_book = {}
    for book_element in soup.find_all('input', {'class': 'livre-input'}):
        parent_element = book_element.find_parent()  # Trouver l'élément parent
        title = parent_element.text.strip()  # Titre du livre à partir de l'élément parent
        prices = {
            'prix_convenable': book_element['data-price'],
            'prix_bon_etat': book_element['data-beprice'],
            'prix_tres_bon_etat': book_element['data-tbeprice']
        }
        prices_by_book[title] = prices

    return prices_by_book


# Obtenir les prix par état depuis la page bundle
prices_by_condition = get_prices_by_condition_bundle()

# URL de la page à scraper
url = 'https://www.collection-ldvelh.fr/books'

# Effectuer une requête HTTP pour obtenir le contenu de la page
response = requests.get(url)
content = response.content

# Utiliser BeautifulSoup pour parser le contenu HTML
soup = BeautifulSoup(content, 'html.parser')

# Trouver tous les éléments qui contiennent les informations des livres
books = soup.find_all('div', {'data-titre': True})

# Liste des numéros de livres possédés avec doublons possibles
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

# Compter le nombre de fois que chaque numéro apparaît
owned_count = Counter(owned_book_numbers)

# Préparer une liste pour stocker les données des livres
books_data = []

# Obtenir la date actuelle
current_date = datetime.now().strftime("%Y-%m-%d")

# Boucle pour extraire les informations de chaque livre
for book in books:
    # Trouver la balise 'a' qui contient le lien vers la page du livre
    book_link = book.find('a', href=True)

    # Extraire l'ISBN à partir de l'URL (le dernier élément après '/')
    isbn = book_link['href'].split('/')[-1] if book_link else None
    book_link = book_link['href'] if book_link else None
    serie_cut = book['data-serie'].split("-")[0].strip() if 'data-serie' in book.attrs else None
    book_info = {
        'titre': book['data-titre'],
        'prix': book['data-prix'],
        'serie': serie_cut,
        'note': book['data-note'],
        'numero': book['data-numero'],
        'own': owned_count[book['data-numero']],
        'date': book['data-date'],
        'isbn': isbn,
        'last_date': current_date,
        'link': book_link
    }
    # Ajouter les prix par état du livre
    title = book['data-titre']
    if title in prices_by_condition:
        book_info.update(prices_by_condition[title])
    else:
        book_info['prix_convenable'] = None
        book_info['prix_bon_etat'] = None
        book_info['prix_tres_bon_etat'] = None
    books_data.append(book_info)


# URL pour les statistiques
stats_url = 'https://www.collection-ldvelh.fr/stats'

# Effectuer une requête HTTP pour obtenir le contenu de la page des stats
stats_response = requests.get(stats_url)
stats_content = stats_response.content

# Utiliser BeautifulSoup pour parser le contenu HTML de la page des stats
stats_soup = BeautifulSoup(stats_content, 'html.parser')

# Pourcentages de collectionneurs possédant chaque livre
collection_percentages = {}
for li in stats_soup.find_all('li', class_='d-flex space-between w-100'):
    book_title = li.find('a', class_='dark-grey').text.strip()
    percentage = li.find('span', class_='col-xs-2 small p-0 right').text.strip().replace('%', '')
    collection_percentages[book_title] = percentage

# Mise à jour avec les pourcentages de collectionneurs
for book in books_data:
    book_title = book['titre']
    if book_title in collection_percentages:
        book['collection_percentage'] = collection_percentages[book_title]
    else:
        book['collection_percentage'] = 'N/A'

# Données des nouveaux livres hors système à ajouter
nouveaux_livres = [
    {'titre': "L'Aventurie", 'prix': 15, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "001", 'own': 2, 'date': None, 'last_date': current_date},
    {'titre': "Le Livre des Règles", 'prix': 15, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "002", 'own': 2, 'date': None, 'last_date': current_date},
    {'titre': "Le Livre des Règles 2", 'prix': 15, 'serie': "L'Œil Noir ", 'note': "5", 'numero': "003", 'own': 2, 'date': None, 'last_date': current_date},
    {'titre': 'Le Livre des Aventures', 'prix': 15, 'serie': "L'Œil Noir    ", 'note': "5", 'numero': "004", 'own': 2, 'date': None, 'last_date': current_date},
    {'titre': 'Héros, Monstres et Forces Obscures', 'prix': 20, 'serie': "L'Œil Noir   ", 'note': "5", 'numero': "005", 'own': 1, 'date': None, 'last_date': current_date}
]

for livre in nouveaux_livres:
    books_data.append(livre)


# Nom du fichier CSV
# Dossier de sortie : data/raw/collection-ldvelh/ (à la racine du dépôt)
output_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw' / 'collection-ldvelh'
output_dir.mkdir(parents=True, exist_ok=True)
filename = output_dir / f'books_data-{current_date}.csv'

# Écriture du CSV en UTF-8
with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
    fieldnames = ['titre', 'prix', 'serie', 'note', 'numero', 'own', 'date', 'isbn', 'last_date', 'link',
                  'collection_percentage', 'prix_convenable', 'prix_bon_etat', 'prix_tres_bon_etat']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for book in books_data:
        writer.writerow(book)

print(f"Les données ont été exportées avec succès dans {filename}")
