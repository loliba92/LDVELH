-- Modèle en étoile : une table de faits (FaitPrix) entourée de dimensions.
PRAGMA foreign_keys = ON;

-- Dimension : calendrier (date de l'observation du prix)
CREATE TABLE DimDate (
    date_key     INTEGER PRIMARY KEY,          -- AAAAMMJJ
    date         TEXT NOT NULL UNIQUE,         -- AAAA-MM-JJ
    annee        INTEGER NOT NULL,
    trimestre    INTEGER NOT NULL,
    mois         INTEGER NOT NULL,
    nom_mois     TEXT NOT NULL,
    annee_mois   TEXT NOT NULL,                -- AAAA-MM
    semaine_iso  INTEGER NOT NULL,
    jour_semaine INTEGER NOT NULL,             -- 1 = lundi
    nom_jour     TEXT NOT NULL
);

-- Dimension : état du livre
CREATE TABLE DimEtat (
    etat_key    INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    libelle     TEXT NOT NULL,
    rang        INTEGER NOT NULL,              -- 0 = inconnu, croissant avec la qualité
    description TEXT
);

-- Dimension : d'où vient le prix
CREATE TABLE DimSource (
    source_key INTEGER PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    nom        TEXT NOT NULL,
    famille    TEXT NOT NULL,                  -- historique / marketplace / perso / rachat / communaute
    acces      TEXT NOT NULL,                  -- fichier / api / saisie
    fiabilite  REAL NOT NULL                   -- 0 à 1, sert au modèle de prix
);

-- Dimension : nature du prix (vente réelle, prix demandé, etc.)
CREATE TABLE DimTypePrix (
    type_key       INTEGER PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    libelle        TEXT NOT NULL,
    poids_modele   REAL NOT NULL,              -- poids dans le calcul de la cote
    est_prix_reel  INTEGER NOT NULL            -- 1 si un acheteur a réellement payé
);

-- Dimension : le livre, au sens du texte, quelle que soit l'édition
CREATE TABLE DimLivre (
    livre_key      INTEGER PRIMARY KEY,
    livre_id       TEXT NOT NULL UNIQUE,       -- identifiant lisible (slug)
    titre          TEXT NOT NULL,
    auteurs        TEXT,
    nb_versions    INTEGER NOT NULL DEFAULT 1
);

-- Dimension : la version (édition précise) d'un livre : V1, V2... V5, autres éditeurs
CREATE TABLE DimVersion (
    version_key          INTEGER PRIMARY KEY,
    id                   TEXT NOT NULL UNIQUE,  -- ISBN-13 ou LOCAL-série-numéro
    isbn13               TEXT,
    isbn10               TEXT,
    livre_key            INTEGER NOT NULL REFERENCES DimLivre(livre_key),
    numero_version       INTEGER NOT NULL,      -- 1 = première version
    libelle_version      TEXT NOT NULL,         -- V1, V2...
    est_derniere_version INTEGER NOT NULL,      -- 1 si la plus récente du livre
    en_vente             INTEGER,               -- 1 = encore vendue neuve, 0 = épuisée, NULL = inconnu
    titre_version        TEXT NOT NULL,         -- titre porté par cette version
    serie                TEXT,                  -- Défis Fantastiques, Loup Solitaire...
    numero_serie         TEXT,
    editeur              TEXT,                  -- Gallimard, Alkonost...
    collection_editeur   TEXT,                  -- Folio Junior...
    annee                INTEGER,               -- année indiquée par collection-ldvelh.fr
    annee_bnf            INTEGER,               -- année de la notice BnF (peut différer : tirages)
    pages                INTEGER,
    traducteur           TEXT,
    illustrateur         TEXT,
    notice_bnf           TEXT,
    statut               TEXT NOT NULL          -- brut / enrichi / vérifié
);

-- Table de faits : un prix observé
CREATE TABLE FaitPrix (
    prix_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    version_key     INTEGER NOT NULL REFERENCES DimVersion(version_key),
    livre_key       INTEGER NOT NULL REFERENCES DimLivre(livre_key),
    etat_key        INTEGER NOT NULL REFERENCES DimEtat(etat_key),
    date_key        INTEGER NOT NULL REFERENCES DimDate(date_key),
    source_key      INTEGER NOT NULL REFERENCES DimSource(source_key),
    type_key        INTEGER NOT NULL REFERENCES DimTypePrix(type_key),
    prix            REAL NOT NULL CHECK (prix >= 0),   -- en euros, hors port
    frais_port      REAL CHECK (frais_port IS NULL OR frais_port >= 0),
    est_lot         INTEGER NOT NULL DEFAULT 0,
    url             TEXT,
    cle_naturelle   TEXT NOT NULL UNIQUE,              -- évite de charger deux fois la même observation
    date_chargement TEXT NOT NULL
);
CREATE INDEX ix_fait_version ON FaitPrix(version_key);
CREATE INDEX ix_fait_livre   ON FaitPrix(livre_key);
CREATE INDEX ix_fait_etat    ON FaitPrix(etat_key);
CREATE INDEX ix_fait_date    ON FaitPrix(date_key);
CREATE INDEX ix_fait_source  ON FaitPrix(source_key);
CREATE INDEX ix_fait_type    ON FaitPrix(type_key);

-- Vue de lecture : tout est déjà joint
CREATE VIEW VueFaitPrix AS
SELECT f.prix_key, d.date, l.titre AS livre, v.libelle_version, v.titre_version, v.id,
       v.serie, v.numero_serie, v.editeur, v.collection_editeur, v.annee AS annee_version,
       v.en_vente, v.est_derniere_version,
       e.libelle AS etat, e.rang AS etat_rang, s.nom AS source, t.libelle AS type_prix,
       t.est_prix_reel, f.prix, f.frais_port, f.est_lot, f.url
FROM FaitPrix f
JOIN DimVersion v ON v.version_key = f.version_key
JOIN DimLivre l   ON l.livre_key   = f.livre_key
JOIN DimEtat e    ON e.etat_key    = f.etat_key
JOIN DimDate d    ON d.date_key    = f.date_key
JOIN DimSource s  ON s.source_key  = f.source_key
JOIN DimTypePrix t ON t.type_key   = f.type_key;

-- Vue de lecture : résumé par version, état et nature du prix
CREATE VIEW VuePrixResume AS
SELECT id, titre_version, libelle_version, etat, type_prix,
       COUNT(*) AS nb, ROUND(MIN(prix), 2) AS prix_min,
       ROUND(AVG(prix), 2) AS prix_moyen, ROUND(MAX(prix), 2) AS prix_max
FROM VueFaitPrix
WHERE est_lot = 0
GROUP BY id, titre_version, libelle_version, etat, type_prix;
