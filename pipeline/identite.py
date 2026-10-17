"""Identité des administrateurs : vérifie la connexion Google jointe à un envoi depuis le site.

La page « Vérifier les prix » transmet au lot GitHub le jeton signé que Google remet à la personne connectée (champ `identite`).
Ce programme le vérifie avec les clés publiques de Google, contrôle qu'il a été émis pour ce site (web/data/admin-config.json,
`client_id`) et que l'adresse figure dans data/admins.json : {"admins": {"adresse@exemple.fr": "Prénom affiché"}}.
L'adresse peut être remplacée par son empreinte, pour ne pas l'écrire en clair dans le dépôt : "sha256:<empreinte sha256 de l'adresse en minuscules>".
Le nom affiché vient de cette liste, pas de la personne : c'est lui qui est enregistré avec la mise à jour.
Sans `client_id`, la vérification n'est pas encore en service : l'envoi reste accepté, sans nom.

Usage (lot GitHub) : IDENTITE=<jeton> python pipeline/identite.py   (écrit AUTEUR=<nom> dans $GITHUB_ENV ; code 1 si refusé)
"""
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ADMINS = RACINE / "data" / "admins.json"
CONFIG = RACINE / "web" / "data" / "admin-config.json"
CERTS = "https://www.googleapis.com/oauth2/v3/certs"
EMETTEURS = ("accounts.google.com", "https://accounts.google.com")


def _lire(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def certificats():
    with urllib.request.urlopen(CERTS, timeout=20) as r:
        return json.load(r)


def verifier(jeton, client_id, admins, certs=None):
    """(nom, None) si le jeton est valable et l'adresse autorisée ; sinon (None, raison)."""
    import jwt
    if not jeton:
        return None, "aucune connexion Google jointe à l'envoi"
    try:
        entete = jwt.get_unverified_header(jeton)
        jeux = jwt.PyJWKSet.from_dict(certs or certificats())
        cle = next((k for k in jeux.keys if k.key_id == entete.get("kid")), None)
        if cle is None:
            return None, "clé de signature inconnue"
        infos = jwt.decode(jeton, cle.key, algorithms=["RS256"], audience=client_id,
                           options={"require": ["exp", "iss", "aud"]}, leeway=30)
    except Exception as e:                                   # signature, audience, expiration, format
        return None, f"jeton refusé ({type(e).__name__})"
    if infos.get("iss") not in EMETTEURS:
        return None, "émetteur inattendu"
    if not infos.get("email_verified"):
        return None, "adresse non vérifiée par Google"
    adresse = str(infos.get("email", "")).strip().lower()
    liste = {str(k).strip().lower(): v for k, v in admins.items()}
    nom = liste.get(adresse) or liste.get("sha256:" + hashlib.sha256(adresse.encode()).hexdigest())
    if not nom:
        return None, "adresse non autorisée"
    return str(nom), None


def main():
    config, liste = _lire(CONFIG), _lire(ADMINS).get("admins", {})
    client_id = config.get("client_id", "")
    if not client_id:
        print("Connexion Google pas encore en service (client_id vide) : envoi accepté sans nom.")
        return 0
    nom, raison = verifier(os.environ.get("IDENTITE", ""), client_id, liste)
    if raison:
        print(f"Envoi refusé : {raison}.", file=sys.stderr)
        return 1
    print(f"Envoi de {nom}.")
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
            f.write(f"AUTEUR={nom}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
