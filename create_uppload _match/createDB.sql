-- Table des joueurs (inchangée)
CREATE TABLE Player (
    player_id serial PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Table des matchs en 1v1
CREATE TABLE Match (
    match_id serial PRIMARY KEY,
    match_timestamp TIMESTAMP NOT NULL,
    -- Remplacement de winning_team_id et losing_team_id par winning_player_id et losing_player_id
    winning_player_id INT NOT NULL REFERENCES Player(player_id),
    losing_player_id INT NOT NULL REFERENCES Player(player_id),
    -- Ici, les scores peuvent être adaptés selon vos règles (par exemple, un match se joue jusqu'à 11 points)
    winning_score INT NOT NULL CHECK (winning_score = 11),
    losing_score INT NOT NULL CHECK (losing_score >= 0 AND losing_score < 11)
);

-- Table de relation entre joueur et match (historique de participation)
CREATE TABLE PlayerMatch (
    player_match_id serial PRIMARY KEY,
    player_id INT NOT NULL REFERENCES Player(player_id),
    match_id INT NOT NULL REFERENCES Match(match_id)
);

-- Table pour l'historique des classements (rating) des joueurs
CREATE TABLE PlayerRating (
    player_rating_id serial PRIMARY KEY,
    player_match_id INT NOT NULL REFERENCES PlayerMatch(player_match_id),
    rating INT NOT NULL,
    player_rating_timestamp TIMESTAMP NOT NULL
);

-- Séquences pour les identifiants des tables des joueurs et des matchs
CREATE SEQUENCE player_id_seq START 1;
CREATE SEQUENCE match_id_seq START 1;
CREATE SEQUENCE player_match_id_seq START 1;
CREATE SEQUENCE player_rating_id_seq START 1;
