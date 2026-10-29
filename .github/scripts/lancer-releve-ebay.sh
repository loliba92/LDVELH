#!/usr/bin/env bash
# Lance le relevé complet des prix eBay (workflow prix-ebay.yml), SAUF si un relevé a déjà réussi aujourd'hui (jour UTC).
# Un relevé complet fait environ 2 400 appels pour une limite habituelle de 5 000 par jour : un second relevé le même jour
# s'arrête sur l'erreur 429 de la limite d'appels, sans rien enregistrer (29 octobre 2026, après l'ajout d'un livre).
# Les livres ajoutés reçoivent alors leur prix eBay au prochain relevé programmé (tous les deux jours).
# Variable GH_TOKEN requise (déjà fournie par les lots qui appellent ce script).
set -u
JOUR="$(date -u +%F)"
FAITS="$(gh run list --workflow prix-ebay.yml --status success --limit 30 --json createdAt \
  --jq "[.[] | select(.createdAt | startswith(\"$JOUR\"))] | length" 2>/dev/null || true)"
if [ -n "${FAITS:-}" ] && [ "$FAITS" -gt 0 ] 2>/dev/null; then
  MSG="Relevé eBay non relancé : $FAITS relevé(s) déjà réussi(s) aujourd'hui (limite d'appels eBay). Les prix des livres ajoutés viendront au prochain relevé programmé."
  echo "$MSG"
  [ -n "${GITHUB_STEP_SUMMARY:-}" ] && echo "$MSG" >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
gh workflow run prix-ebay.yml
