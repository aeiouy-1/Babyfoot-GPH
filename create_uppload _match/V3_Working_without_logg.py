import psycopg2
from openpyxl import load_workbook
from config import DATABASE_CONFIG
import math
import logging

# Set up logging to a file
logging.basicConfig(filename='elo_log.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Connect to the database
conn = psycopg2.connect(
    host=DATABASE_CONFIG['host'],
    database=DATABASE_CONFIG['database'],
    user=DATABASE_CONFIG['user'],
    password=DATABASE_CONFIG['password']
)
print("Connected to the database!")

print("Working...")
# Create a cursor
cur = conn.cursor()

# Load the workbook
wb = load_workbook('data.xlsx')

# Select the active sheet
ws = wb.active

def get_player_match_id_by_timestamp_and_by_player_id(player1_id, player2_id, match_date, cur):
    """
    Récupère les IDs des relations joueur-match pour un match 1v1 à une date donnée.
    
    Paramètres :
      - player1_id : ID du premier joueur
      - player2_id : ID du second joueur
      - match_date : date et heure du match (format string, ex. '2025-03-02 21:32:46')
      - cur : curseur de la connexion à la base de données
      
    Retourne :
      - Un tuple (player1_match_id, player2_match_id)
    """
    # Récupérer l'ID de la relation pour le premier joueur
    cur.execute(
        "SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id "
        "WHERE PlayerMatch.player_id = %s AND Match.match_timestamp = %s;",
        (player1_id, match_date)
    )
    player1_match_id = cur.fetchone()[0]
    
    # Récupérer l'ID de la relation pour le second joueur
    cur.execute(
        "SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id "
        "WHERE PlayerMatch.player_id = %s AND Match.match_timestamp = %s;",
        (player2_id, match_date)
    )
    player2_match_id = cur.fetchone()[0]
    
    return (player1_match_id, player2_match_id)


# Get the player ID of the players playing a match
def get_player_id(player1_name, player2_name, cur):
    """
    Récupère l'ID de deux joueurs à partir de leur prénom.
    
    Paramètres :
      - player1_name : prénom du premier joueur
      - player2_name : prénom du second joueur
      - cur : curseur de la connexion à la base de données
      
    Retourne :
      - Un tuple contenant (player1_id, player2_id)
    """
    # Récupère l'ID du premier joueur depuis la table 'player'
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player1_name,))
    player1_id = cur.fetchone()[0]
    logging.info('Processing player1 %s with id %s', player1_name, player1_id)

    # Récupère l'ID du second joueur depuis la table 'player'
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player2_name,))
    player2_id = cur.fetchone()[0]
    logging.info('Processing player2 %s with id %s', player2_name, player2_id)

    # Retourne un tuple contenant les IDs des deux joueurs
    return (player1_id, player2_id)

        

def number_of_games_player(player1_id, player2_id, match_date, cur):
    """
    Retourne le nombre de matchs joués par chacun des deux joueurs (mode 1v1)
    jusqu'à la date donnée.
    
    Paramètres :
      - player1_id : l'ID du premier joueur
      - player2_id : l'ID du second joueur
      - match_date : la date limite (chaîne au format 'YYYY-MM-DD HH:MM:SS')
      - cur : le curseur de la connexion à la base de données
      
    Retourne :
      - Un tuple (nombre_de_matchs_joueur1, nombre_de_matchs_joueur2)
    """
    # Récupère le nombre de matchs pour le premier joueur
    cur.execute(
        "SELECT COUNT(*) FROM PlayerMatch pm INNER JOIN Match m ON pm.match_id = m.match_id WHERE pm.player_id = %s AND m.match_timestamp <= %s;",
        (player1_id, match_date)
    )
    number_of_game_player1 = cur.fetchone()[0] or 0
    # Journalisation pour le premier joueur
    logging.info(f"Nombre de matchs pour le joueur avec id {player1_id} à la date {match_date} : {number_of_game_player1}")

    # Récupère le nombre de matchs pour le second joueur
    cur.execute(
        "SELECT COUNT(*) FROM PlayerMatch pm INNER JOIN Match m ON pm.match_id = m.match_id WHERE pm.player_id = %s AND m.match_timestamp <= %s;",
        (player2_id, match_date)
    )
    number_of_game_player2 = cur.fetchone()[0] or 0
    # Journalisation pour le second joueur
    logging.info(f"Nombre de matchs pour le joueur avec id {player2_id} à la date {match_date} : {number_of_game_player2}")

    return (number_of_game_player1, number_of_game_player2)


             
def get_player_ratings(player1_id, player2_id, cur):
    """
    Récupère le classement actuel des deux joueurs pour un match 1v1.
    
    Paramètres :
      - player1_id : ID du premier joueur
      - player2_id : ID du second joueur
      - cur : curseur de la connexion à la base de données
      
    Retourne :
      - Un tuple (player1_rating, player2_rating)
      Si aucun classement n'est trouvé, la valeur par défaut 1500 est utilisée.
    """
    # Récupération du classement du premier joueur
    cur.execute(
        "SELECT rating, player_rating_timestamp FROM playerrating WHERE player_match_id IN "
        "(SELECT player_match_id FROM playermatch WHERE player_id = %s) "
        "ORDER BY player_rating_timestamp DESC LIMIT 1;",
        (player1_id,)
    )
    result = cur.fetchone()
    if result is not None:
        player1_rating = result[0]
    else:
        player1_rating = 1500
    # Journalisation avec l'ID, puisque le nom n'est pas passé ici
    logging.info(f"Current rating of player with id {player1_id} is {player1_rating}")

    # Récupération du classement du second joueur
    cur.execute(
        "SELECT rating, player_rating_timestamp FROM playerrating WHERE player_match_id IN "
        "(SELECT player_match_id FROM playermatch WHERE player_id = %s) "
        "ORDER BY player_rating_timestamp DESC LIMIT 1;",
        (player2_id,)
    )
    result = cur.fetchone()
    if result is not None:
        player2_rating = result[0]
    else:
        player2_rating = 1500
    logging.info(f"Current rating of player with id {player2_id} is {player2_rating}")

    return player1_rating, player2_rating


# Get the point factor 
def calculate_point_factor(score_difference):
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3

# Iterate through the rows of the sheet
for row in ws.rows:

    # checking if the rows are not null
    if all(cell.value == None for cell in row):
        break
    date = row[0].value
    player1_name = row[1].value
    player2_name = row[2].value
    player1_score = row[3].value
    player2_score = row[4].value

    logging.info('Processing match %s', date)
    
    # Call the get_player_id function inside the loop
    player1_id, player2_id,= get_player_id(player1_name, player2_name, cur)

    # Call the number_of_games_player function inside the loop
    number_of_game_player1, number_of_game_player2 = number_of_games_player(player1_id, player2_id, date, cur)

    # Call the get_player_ratings function inside the loop
    player1_rating, player2_rating = get_player_ratings(player1_id, player2_id, cur)

    # Call the get_player_match_id_by_timestamp_and_by_player_id function inside the loop
    player_match1_id, player_match2_id = get_player_match_id_by_timestamp_and_by_player_id(player1_id, player2_id, date, cur)
    
    # Calculate the expected scores for the players
    player1_expected_score_against_player2 = 1 / (1 + 10**((player2_rating - player1_rating) / 500))
    player2_expected_score_against_player1 = 1 / (1 + 10**((player1_rating - player2_rating) / 500))
    player1_expected_score = player1_expected_score_against_player2
    player2_expected_score = player2_expected_score_against_player1
    logging.info('Player %s expected score against player %s: %s',player1_name, player2_name, player1_expected_score_against_player2)
    logging.info('Player %s expected score against player %s: %s', player2_name, player1_name,player2_expected_score_against_player1)
    logging.info('Player %s overall expected score: %s',player1_name, player1_expected_score)
    logging.info('Player %s overall expected score: %s',player2_name, player2_expected_score)

    # Calculate the point factor to be used as a variable
    score_difference = abs(player1_score - player2_score)
    point_factor = calculate_point_factor(score_difference)
    logging.info("Point factor: %s", point_factor)

    # Calculate the K value for each player based on the number of games played and their rating
    k1 = 50 / (1 + number_of_game_player1 / 300)
    k2 = 50 / (1 + number_of_game_player2 / 300) 

    #delta = 32 * (1 - winnerChanceToWin)
    logging.info('Player %s K value: %s', player1_name,k1)
    logging.info('Player %s K value: %s', player2_name,k2)


 #logg the wining player
    if player1_score > player1_score:
        player1_actual_score = 1
        player2_actual_score = 0
        logging.info('player 1 win with %s and : %s', player1_name)
        logging.info('player 2 lost with %s and : %s', player2_name)

    else:
        player1_actual_score = 0
        player2_actual_score = 1
        logging.info('player 1 lost with %s and : %s', player1_name)
        logging.info('player 2 win with %s and : %s', player2_name)
        
    # Calculate the new Elo ratings for each player
    player1_new_rating = player1_rating + k1 * point_factor  * (team1_actual_score - player1_expected_score)
    player2_new_rating = player2_rating + k2 * point_factor  * (team1_actual_score - player2_expected_score)
    
    # Log the new ratings
    logging.info('player1_new_rating = player1_rating + k1 * point_factor * weighting_factor_player1 * (team1_actual_score - player1_expected_score')
    logging.info('%s new rating: %s = %s + %s * %s * (%s - %s)', player1_name, player1_new_rating, player1_rating, k1, point_factor, player1_actual_score, player1_expected_score)
    logging.info('%s new rating: %s = %s + %s * %s * (%s - %s)', player2_name, player2_new_rating, player2_rating, k2, point_factor, player2_actual_score, player2_expected_score)
   

    # Update the database with the player ratings
    cur.execute("INSERT INTO playerrating (player_match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s)", (player_match1_id, player1_new_rating, date))
    cur.execute("INSERT INTO playerrating (player_match_id, rating, player_rating_timestamp) VALUES ( %s, %s, %s)", (player_match2_id, player2_new_rating, date))
    logging.info('Insert player in database :%s with rating %s on the %s',player1_name,player1_new_rating, date)
    logging.info('Insert player in database :%s with rating %s on the %s',player2_name,player2_new_rating, date)

    conn.commit()
    logging.info('_________________')

# Close the cursor and connection
print("Done !")
cur.close()
conn.close()