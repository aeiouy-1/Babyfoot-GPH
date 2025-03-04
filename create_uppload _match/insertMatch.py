import psycopg2
from openpyxl import load_workbook
from config import DATABASE_CONFIG
import math
import logging

# Configuration du logging pour enregistrer les informations dans un fichier
logging.basicConfig(filename='elo_log.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Connexion à la base de données
conn = psycopg2.connect(
    host=DATABASE_CONFIG['host'],
    database=DATABASE_CONFIG['database'],
    user=DATABASE_CONFIG['user'],
    password=DATABASE_CONFIG['password']
)
print("Connected to the database!")

print("Working...")
# Création d'un curseur pour exécuter les requêtes SQL
cur = conn.cursor()

# Chargement du workbook Excel
wb = load_workbook('data.xlsx')

# Sélection de la feuille active
ws = wb.active

# Fonction pour déterminer le gagnant d'un match 1v1
def get_winning_player(player1_score, player2_score):
    if player1_score > player2_score:
        return 1
    elif player2_score > player1_score:
        return 2
    else:
        return 0  # Match nul

# Itération sur les lignes du fichier Excel
for row in ws.rows:

    # Vérifier que la ligne n'est pas vide
    if all(cell.value is None for cell in row):
        break

    # Extraction des données : date, noms des deux joueurs et leurs scores
    date = row[0].value
    player1_name = row[1].value
    player2_name = row[2].value
    player1_score = row[3].value
    player2_score = row[4].value

    logging.info('Processing match %s', date)
    
    # --- Gestion des joueurs ---
    # Pour le premier joueur
    if player1_name:
        cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player1_name,))
        player1_id = cur.fetchone()
        if player1_id is None:
            # Si le joueur n'existe pas, le créer en générant un nouvel ID
            cur.execute("SELECT nextval('player_id_seq')")
            new_id = cur.fetchone()[0]
            cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (new_id, player1_name))
            player1_id = new_id
        else:
            player1_id = player1_id[0]
    else:
        continue  # Si le nom du joueur est vide, on passe à la ligne suivante

    # Pour le second joueur
    if player2_name:
        cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player2_name,))
        player2_id = cur.fetchone()
        if player2_id is None:
            cur.execute("SELECT nextval('player_id_seq')")
            new_id = cur.fetchone()[0]
            cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (new_id, player2_name))
            player2_id = new_id
        else:
            player2_id = player2_id[0]
    else:
        continue

    # Valider les éventuelles insertions de joueurs
    conn.commit()

    # --- Détermination du gagnant du match 1v1 ---
    # On utilise la fonction get_winning_player pour déterminer le gagnant
    winning_player = get_winning_player(player1_score, player2_score)

    if winning_player == 1:
        winning_player_id = player1_id
        losing_player_id = player2_id
        winning_player_score = player1_score
        losing_player_score = player2_score
    elif winning_player == 2:
        winning_player_id = player2_id
        losing_player_id = player1_id
        winning_player_score = player2_score
        losing_player_score = player1_score
    else:
        winning_player_id = None
        losing_player_id = None
        winning_player_score = None
        losing_player_score = None  

    # Vérifier si le match existe déjà pour éviter les doublons
    cur.execute(
        "SELECT * FROM match WHERE match_timestamp=%s AND winning_player_id=%s AND losing_player_id=%s AND winning_score=%s AND losing_score=%s",
        (date, winning_player_id, losing_player_id, winning_player_score, losing_player_score)
    )
    match = cur.fetchone()
    if match is None:
        # Insertion du match dans la table Match
        cur.execute(
            "INSERT INTO match (match_timestamp, winning_player_id, losing_player_id, winning_score, losing_score) VALUES (%s, %s, %s, %s, %s)",
            (date, winning_player_id, losing_player_id, winning_player_score, losing_player_score)
        )
        print(f'Processing match: {date} with {player1_name} vs {player2_name}: {player1_score} - {player2_score}')
        conn.commit()

        # Récupérer l'ID du match inséré
        cur.execute("SELECT match_id FROM match ORDER BY match_id DESC LIMIT 1")
        match_id = cur.fetchone()[0]
          
        # Insérer les relations dans la table PlayerMatch pour le match 1v1
        cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player1_id, match_id))
        cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player2_id, match_id))
  
    else:
        print(f'Skipping match: {date} with {player1_name} vs {player2_name}: {player1_score} - {player2_score}, the match already exists')

    conn.commit()

# Fermeture de la connexion à la base de données
cur.close()
conn.close()

print("Done!")
