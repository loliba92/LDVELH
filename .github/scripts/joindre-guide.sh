#!/usr/bin/env bash
# Joint à la sortie de publication le dernier guide PDF généré (workflow guide-pdf.yml), sans le régénérer.
# Usage : .github/scripts/joindre-guide.sh <dossier de sortie, ex. _site> <fichier du jeton>
# Ne fait JAMAIS échouer la publication : sans guide récent (première fois, artefact expiré, erreur de téléchargement), rien n'est joint et le bouton reste caché.
set -u
sortie="$1"; jeton_fichier="$2"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
jeton="$(tr -d '[:space:]' < "$jeton_fichier" 2>/dev/null)"
[ -n "$jeton" ] || { echo "Guide : pas de jeton, rien à joindre."; exit 0; }
id="$(gh run list --workflow guide-pdf.yml --status success --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null)"
[ -n "$id" ] && [ "$id" != "null" ] || { echo "Guide : aucune génération réussie, publication sans guide."; exit 0; }
gh run download "$id" --name guide-pdf --dir "$tmp" >/dev/null 2>&1 || { echo "Guide : artefact absent ou expiré, publication sans guide."; exit 0; }
[ -s "$tmp/guide-reference.pdf" ] && [ -s "$tmp/date.txt" ] || { echo "Guide : artefact incomplet, publication sans guide."; exit 0; }
date_guide="$(tr -d '[:space:]' < "$tmp/date.txt")"
mkdir -p "$sortie/data"
cp "$tmp/guide-reference.pdf" "$sortie/guide-reference-$jeton.pdf"
printf '{"fichier":"guide-reference-%s.pdf","date":"%s"}\n' "$jeton" "$date_guide" > "$sortie/data/guide.json"
echo "Guide joint (généré le $date_guide)."
