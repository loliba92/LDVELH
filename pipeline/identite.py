"""Identité des administrateurs : vérifie la connexion Google jointe à un envoi depuis le site.

La page « Vérifier les prix » transmet au lot GitHub le jeton signé que Google remet à la personne connectée (champ `identite`).
Ce programme le vérifie avec les clés publiques de Google et contrôle qu'il a été émis pour ce site (web/data/admin-config.json,
`client_id`). Il sert à savoir QUI envoie ; l'autorisation d'envoyer vient de la clé GitHub, que le propriétaire ne donne qu'aux personnes
de son choix. Fichier data/admins.json :
  "ouvert"  : true = tout compte Google vérifié est accepté (le propriétaire reste maître de la clé) ; false = seules les adresses de "noms".
  "equipe"  : adresse (ou son empreinte) -> {"nom": nom à afficher, "role": "admin" | "superadmin"}. Le nom prime sur celui du compte Google.
              (l'ancienne rubrique "noms" : adresse -> nom, reste lue.)
  "relais"  : true quand les envois passent par le relais (relais/) : le relais a déjà vérifié la personne et transmet son nom dans l'entrée
              `auteur` du lot ; plus aucune connexion Google n'est alors jointe. À n'activer qu'après avoir supprimé l'ancienne clé commune.
  "bloques" : adresses (ou empreintes) refusées même avec la clé.
L'adresse peut être remplacée par l'empreinte sha256 de l'adresse en minuscules : "sha256:<empreinte>", pour ne pas l'écrire en clair dans le dépôt.
Sans entrée dans "noms", le nom est celui du compte Google suivi de quatre signes tirés de l'adresse (« Marie #3fa2 ») : il ne peut pas
se faire passer pour un nom de la liste.
Sans `client_id`, la vérification n'est pas encore en service : l'envoi reste accepté, sans nom.

Usage (lot GitHub) : IDENTITE=<jeton> python pipeline/identite.py   (écrit AUTEUR=<nom> dans $GITHUB_ENV ; code 1 si refusé)
"""
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validations

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


def _empreinte(adresse):
    return "sha256:" + hashlib.sha256(adresse.encode()).hexdigest()


def _cle(entree):
    return str(entree).strip().lower()


def verifier(jeton, client_id, noms, certs=None, ouvert=False, bloques=()):
    """(nom, None) si le jeton est valable et la personne acceptée ; sinon (None, raison)."""
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
    adresse = _cle(infos.get("email", ""))
    empreinte = _empreinte(adresse)
    if {adresse, empreinte} & {_cle(b) for b in bloques}:
        return None, "adresse bloquée"
    liste = {_cle(k): v for k, v in noms.items()}
    nom = liste.get(adresse) or liste.get(empreinte)
    if nom:
        return str(nom), None
    if not ouvert:
        return None, "adresse non autorisée"
    prenom = validations.nom_propre(infos.get("given_name") or infos.get("name") or adresse.split("@")[0])[:20] or "Admin"
    return f"{prenom} #{empreinte[7:11]}", None


def main():
    config, fichier = _lire(CONFIG), _lire(ADMINS)
    client_id = config.get("client_id", "")
    if not client_id:
        print("Connexion Google pas encore en service (client_id vide) : envoi accepté sans nom.")
        return 0
    if fichier.get("relais"):
        nom = validations.nom_propre(os.environ.get("AUTEUR_RELAIS", ""))
        if not nom:
            print("Envoi refusé : le relais n'a transmis aucun nom.", file=sys.stderr)
            return 1
        print(f"Envoi de {nom} (via le relais).")
        if os.environ.get("GITHUB_ENV"):
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
                f.write(f"AUTEUR={nom}\n")
        return 0
    noms = dict(fichier.get("noms", {}))
    noms.update({k: m.get("nom", "") for k, m in fichier.get("equipe", {}).items() if isinstance(m, dict) and m.get("nom")})
    nom, raison = verifier(os.environ.get("IDENTITE", ""), client_id, noms,
                           ouvert=bool(fichier.get("ouvert")), bloques=fichier.get("bloques", []))
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
