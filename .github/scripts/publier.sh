#!/usr/bin/env bash
# Publie le travail d'un lot sur main, même si main a avancé pendant qu'il tournait.
#
# Constaté le 17 octobre 2026 : « Corriger des cotes » échouait (« rejected … fetch first ») quand un autre changement arrivait sur main
# entre le début du lot et son envoi, et les corrections n'étaient alors jamais enregistrées. Le relevé eBay (une demi-heure) y est encore
# plus exposé.
#
# Usage :  REJOUER='commande' .github/scripts/publier.sh "message de commit" chemin...
#   1. commit des chemins donnés ; 2. envoi ; 3. si main a avancé : on se remet sur la dernière version et on repousse (sans conflit) ;
#   4. en cas de conflit (fichiers générés modifiés des deux côtés) : on repart de la dernière version de main et on exécute REJOUER, qui
#      refait le travail du lot sur cette base (la variable MON_COMMIT donne le commit local d'origine, pour en reprendre des fichiers).
set -u
message="$1"; shift
git add "$@"
if git diff --cached --quiet; then echo "Rien de nouveau."; exit 0; fi
git commit -q -m "$message"
for essai in 1 2 3 4 5; do
  git push && exit 0
  echo "main a avancé pendant le lot (essai $essai) : reprise depuis la dernière version."
  git fetch -q origin main || { sleep 5; continue; }
  if git rebase origin/main; then continue; fi
  git rebase --abort
  export MON_COMMIT="$(git rev-parse HEAD)"
  git reset -q --hard origin/main
  if [ -n "${REJOUER:-}" ]; then bash -ec "$REJOUER" || { echo "La reprise a échoué."; exit 1; }; fi
  git add "$@"
  if git diff --cached --quiet; then echo "Rien de nouveau après la reprise."; exit 0; fi
  git commit -q -m "$message"
done
echo "Envoi impossible après plusieurs essais." >&2
exit 1
