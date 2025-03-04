from flask import Flask, render_template, request, redirect, url_for, abort
import psycopg2
from config import DATABASE_CONFIG
from datetime import datetime, date, timedelta
import math
from flask import Flask
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from sqlalchemy import create_engine
from config import DATABASE_CONFIG
import dash_bootstrap_components as dbc
import sys
import os
import pytz






app = Flask(__name__, template_folder='Templates')


def get_player_match_id_by_timestamp_and_by_player_id(player_id, match_date, cur):
    # Requête pour récupérer l'ID de la relation dans la table PlayerMatch
    cur.execute(
        "SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id WHERE PlayerMatch.player_id = %s AND Match.match_timestamp = %s;",
        (player_id, match_date)
    )
    result = cur.fetchone()
    return result[0] if result is not None else None

# Get the player ID of the players playing a match
def get_player_ids(player1_name, player2_name, cur):
    # Récupérer l'ID du premier joueur
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player1_name,))
    player1_id = cur.fetchone()[0]
    # Récupérer l'ID du second joueur
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player2_name,))
    player2_id = cur.fetchone()[0]
    return player1_id, player2_id

       

def get_player_ratings(player1_id, player2_id, cur):
    # Récupération du classement du premier joueur
    cur.execute(
        "SELECT rating, player_rating_timestamp FROM playerrating WHERE player_match_id IN (SELECT player_match_id FROM playermatch WHERE player_id = %s) ORDER BY player_rating_timestamp DESC LIMIT 1;",
        (player1_id,)
    )
    result = cur.fetchone()
    player1_rating = result[0] if result is not None else 1500

    # Récupération du classement du second joueur
    cur.execute(
        "SELECT rating, player_rating_timestamp FROM playerrating WHERE player_match_id IN (SELECT player_match_id FROM playermatch WHERE player_id = %s) ORDER BY player_rating_timestamp DESC LIMIT 1;",
        (player2_id,)
    )
    result = cur.fetchone()
    player2_rating = result[0] if result is not None else 1500

    return player1_rating, player2_rating

# Get the point factor 
def calculate_point_factor(score_difference):
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3

# Function to process the form data and update the database

def process_game_data(player1_name, player2_name, score1, score2, match_date):
    """
    Traite les données d'un match 1v1 et met à jour la base de données.
    
    Paramètres :
      - player1_name : prénom du premier joueur
      - player2_name : prénom du second joueur
      - score1 : score du premier joueur
      - score2 : score du second joueur
      - match_date : date et heure du match (format string)
    """
    # Connexion à la base de données
    conn = psycopg2.connect(
        host=DATABASE_CONFIG['host'],
        database=DATABASE_CONFIG['database'],
        user=DATABASE_CONFIG['user'],
        password=DATABASE_CONFIG['password']
    )
    cur = conn.cursor()
    
    # --- Gestion des joueurs ---
    # Vérifier et insérer le premier joueur s'il n'existe pas
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player1_name,))
    result = cur.fetchone()
    if result is None:
        cur.execute("SELECT nextval('player_id_seq')")
        new_id = cur.fetchone()[0]
        cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (new_id, player1_name))
        player1_id = new_id
    else:
        player1_id = result[0]
    
    # Vérifier et insérer le second joueur s'il n'existe pas
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player2_name,))
    result = cur.fetchone()
    if result is None:
        cur.execute("SELECT nextval('player_id_seq')")
        new_id = cur.fetchone()[0]
        cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (new_id, player2_name))
        player2_id = new_id
    else:
        player2_id = result[0]
    
    conn.commit()  # Valider les insertions éventuelles
    
    # --- Calcul du match ---
    # Déterminer le gagnant et le perdant en fonction des scores
    if score1 > score2:
        winner_id = player1_id
        loser_id = player2_id
    elif score2 > score1:
        winner_id = player2_id
        loser_id = player1_id
    else:
        # En cas d'égalité, on considère un match nul
        winner_id = None
        loser_id = None

    # Définir les scores gagnant et perdant
    winning_score = max(score1, score2)
    losing_score = min(score1, score2)
    
    # Calcul d'un facteur en fonction de la différence de score (optionnel, ici utilisé pour amplifier les écarts)
    point_factor = 2 + (math.log(abs(score1 - score2) + 1) / math.log(10)) ** 3
    
    # --- Calcul du classement Elo ---
    # Récupérer le classement actuel du premier joueur
    cur.execute("SELECT rating FROM playerrating WHERE player_id=%s ORDER BY player_rating_timestamp DESC LIMIT 1", (player1_id,))
    result = cur.fetchone()
    rating1 = result[0] if result is not None else 1500
    
    # Récupérer le classement actuel du second joueur
    cur.execute("SELECT rating FROM playerrating WHERE player_id=%s ORDER BY player_rating_timestamp DESC LIMIT 1", (player2_id,))
    result = cur.fetchone()
    rating2 = result[0] if result is not None else 1500
    
    # Calcul des scores attendus selon la formule Elo
    expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    expected2 = 1 - expected1
    
    # En cas de match nul, on attribue 0.5 à chacun ; sinon 1 pour le gagnant, 0 pour le perdant
    if winner_id is None:
        actual1 = 0.5
        actual2 = 0.5
    else:
        actual1 = 1 if player1_id == winner_id else 0
        actual2 = 1 if player2_id == winner_id else 0
    
    k = 32  # Constante K
    # Calcul des nouveaux classements Elo avec le facteur de points\n    new_rating1 = rating1 + k * point_factor * (actual1 - expected1)\n    new_rating2 = rating2 + k * point_factor * (actual2 - expected2)
    new_rating1 = rating1 + k * point_factor * (actual1 - expected1)
    new_rating2 = rating2 + k * point_factor * (actual2 - expected2)
    
    # --- Insertion du match dans la base ---
    # On insère le match dans la table Match et on récupère l'ID généré
    cur.execute(
        "INSERT INTO match (match_timestamp, winning_player_id, losing_player_id, winning_score, losing_score) VALUES (%s, %s, %s, %s, %s) RETURNING match_id",
        (match_date, winner_id, loser_id, winning_score, losing_score)
    )
    match_id = cur.fetchone()[0]
    
    # Insertion dans la table PlayerMatch pour enregistrer la participation de chaque joueur\n    cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player1_id, match_id))\n    cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player2_id, match_id))
    cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player1_id, match_id))
    cur.execute("INSERT INTO playermatch (player_id, match_id) VALUES (%s, %s)", (player2_id, match_id))
    
    # Mise à jour des classements dans la table PlayerRating pour chaque joueur\n    cur.execute("INSERT INTO playerrating (player_id, match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s, %s)", (player1_id, match_id, new_rating1, match_date))\n    cur.execute("INSERT INTO playerrating (player_id, match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s, %s)", (player2_id, match_id, new_rating2, match_date))
    cur.execute("INSERT INTO playerrating (player_id, match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s, %s)", (player1_id, match_id, new_rating1, match_date))
    cur.execute("INSERT INTO playerrating (player_id, match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s, %s)", (player2_id, match_id, new_rating2, match_date))
    
    # Valider les changements et fermer la connexion
    conn.commit()

# Get the exptected score for odds   
def calculate_expected_score(player1_name, player2_name):
    """
    Calcule les scores attendus et les cotes (quotations) pour un match 1v1 en utilisant la formule Elo.
    
    Paramètres :
      - player1_name : prénom du premier joueur
      - player2_name : prénom du second joueur
      
    Retourne :
      - expected1 : score attendu pour le premier joueur
      - expected2 : score attendu pour le second joueur
      - odd1 : cote (quotation) pour le premier joueur (inverse du score attendu)
      - odd2 : cote (quotation) pour le second joueur (inverse du score attendu)
    """
    # Connexion à la base de données
    conn = psycopg2.connect(
        host=DATABASE_CONFIG['host'],
        database=DATABASE_CONFIG['database'],
        user=DATABASE_CONFIG['user'],
        password=DATABASE_CONFIG['password']
    )
    cur = conn.cursor()
    
    # Récupération de l'ID du premier joueur
    cur.execute("SELECT player_id FROM player WHERE first_name = %s", (player1_name,))
    result = cur.fetchone()
    if result is None:
        # Si le joueur n'existe pas, on l'insère dans la table player
        cur.execute("SELECT nextval('player_id_seq')")
        player1_id = cur.fetchone()[0]
        cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (player1_id, player1_name))
    else:
        player1_id = result[0]
    
    # Récupération de l'ID du second joueur
    cur.execute("SELECT player_id FROM player WHERE first_name = %s", (player2_name,))
    result = cur.fetchone()
    if result is None:
        # Si le joueur n'existe pas, on l'insère dans la table player
        cur.execute("SELECT nextval('player_id_seq')")
        player2_id = cur.fetchone()[0]
        cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (player2_id, player2_name))
    else:
        player2_id = result[0]
    
    # Valider les éventuelles insertions
    conn.commit()
    
    # Récupérer le classement actuel du premier joueur
    cur.execute("SELECT rating FROM playerrating WHERE player_id = %s ORDER BY player_rating_timestamp DESC LIMIT 1", (player1_id,))
    result = cur.fetchone()
    player1_rating = result[0] if result is not None else 1500

    # Récupérer le classement actuel du second joueur
    cur.execute("SELECT rating FROM playerrating WHERE player_id = %s ORDER BY player_rating_timestamp DESC LIMIT 1", (player2_id,))
    result = cur.fetchone()
    player2_rating = result[0] if result is not None else 1500
    
    # Calcul des scores attendus selon la formule Elo
    # expected1 = 1 / (1 + 10^((rating2 - rating1)/400))
    expected1 = 1 / (1 + 10 ** ((player2_rating - player1_rating) / 400))
    expected2 = 1 - expected1

    # Calcul simple des cotes (quotations) : on prend l'inverse du score attendu
    odd1 = 1 / expected1 if expected1 != 0 else None
    odd2 = 1 / expected2 if expected2 != 0 else None

    # Affichage pour vérification et débogage
    print(f"Player 1 ({player1_name}) expected score: {expected1}")
    print(f"Player 2 ({player2_name}) expected score: {expected2}")
    print(f"Odds for {player1_name}: {odd1}")
    print(f"Odds for {player2_name}: {odd2}")

    # Fermeture de la connexion à la base de données
    cur.close()
    conn.close()

    return expected1, expected2, odd1, odd2



# Get the players from the database
def get_players():
    try:
        conn = psycopg2.connect(
            host=DATABASE_CONFIG['host'],
            database=DATABASE_CONFIG['database'],
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password']
        )
        cursor = conn.cursor()
        query = "SELECT first_name FROM player WHERE active = true ORDER BY first_name ASC;"  # 
        cursor.execute(query)
        players = cursor.fetchall()
        print("Players fetched:", players)  # Add this line to print the fetched players
        return [player[0] for player in players]
       
    except Exception as e:
        print("Error connecting to the database:", e)
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_players_full_list():
    query = 'SELECT first_name FROM player ORDER BY first_name ASC'
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute(query)
        players_full = cur.fetchall()

    return [player[0] for player in players_full]

def get_players_detailed_list():
    query = 'SELECT player_id, first_name, last_name, active FROM player ORDER BY first_name ASC'
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute(query)
        players_full = cur.fetchall()

    return players_full


def get_latest_player_ratings(month=None, year=None):
    now = datetime.now()
    default_month = now.month
    default_year = now.year
    selected_year = int(year) if year else default_year
    selected_month = int(month) if month else default_month
    start_date = f'{selected_year}-{selected_month:02d}-01 00:00:00'
    end_date = f'{selected_year}-{selected_month:02d}-{get_last_day_of_month(selected_month, selected_year):02d} 23:59:59'

    query = '''
        WITH max_player_rating_timestamp AS (
            SELECT 
                pm.player_id,
                MAX(pr.player_rating_timestamp) as max_timestamp
            FROM PlayerMatch pm
            JOIN PlayerRating pr ON pm.player_match_id = pr.player_match_id
            WHERE pr.player_rating_timestamp BETWEEN %s AND %s
            GROUP BY pm.player_id
        ),
        filtered_player_match AS (
            SELECT 
                pm.player_id,
                pm.match_id
            FROM PlayerMatch pm
            JOIN max_player_rating_timestamp mprt ON pm.player_id = mprt.player_id
        ),
        filtered_matches AS (
            SELECT match_id
            FROM Match
            WHERE match_timestamp BETWEEN %s AND %s
        )
        SELECT 
            CONCAT(p.first_name, '.', SUBSTRING(p.last_name FROM 1 FOR 1)) as player_name, 
            pr.rating, 
            COUNT(DISTINCT fpm.match_id) as num_matches,
            pr.player_rating_timestamp
        FROM Player p
        JOIN max_player_rating_timestamp mprt ON p.player_id = mprt.player_id
        JOIN PlayerMatch pm ON p.player_id = pm.player_id
        JOIN PlayerRating pr ON pm.player_match_id = pr.player_match_id
            AND pr.player_rating_timestamp = mprt.max_timestamp
        JOIN filtered_player_match fpm ON p.player_id = fpm.player_id
        JOIN filtered_matches fm ON fpm.match_id = fm.match_id
        GROUP BY p.player_id, pr.rating, pr.player_rating_timestamp
        ORDER BY pr.rating DESC;
    '''

    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute(query, (start_date, end_date, start_date, end_date))
        player_ratings = cur.fetchall()


    return player_ratings

def get_match_list(month=None):
    # Récupération de la date actuelle et définition du mois/année par défaut
    now = datetime.now()
    default_month = now.month
    default_year = now.year
    selected_month = int(month) if month else default_month
    
    # Définition de la période de sélection
    start_date = f'{default_year}-{selected_month:02d}-01 00:00:00'
    end_date = f'{default_year}-{selected_month:02d}-{get_last_day_of_month(selected_month, default_year):02d} 23:59:59'
    
    # Requête SQL adaptée au mode 1v1 :
    # On récupère l'ID du match, le prénom du gagnant, le prénom du perdant, les scores et la date du match.
    query = '''
        SELECT 
            m.match_id AS ID,
            P1.first_name AS winner,
            P2.first_name AS loser,
            m.winning_score,
            m.losing_score,
            m.match_timestamp
        FROM Match m
        JOIN Player P1 ON m.winning_player_id = P1.player_id
        JOIN Player P2 ON m.losing_player_id = P2.player_id
        WHERE m.match_timestamp >= %s AND m.match_timestamp <= %s
        ORDER BY m.match_timestamp DESC;
    '''
    
    # Utilisation d'un gestionnaire de contexte pour la connexion qui se ferme automatiquement
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute(query, (start_date, end_date))
        print(start_date, end_date)  # Affichage des bornes de date pour vérification
        matches = cur.fetchall()
    
    return matches




def get_last_day_of_month(month, year):
    if month == 12:
        return 31
    else:
        return (date(year, month+1, 1) - timedelta(days=1)).day

# Set the time zone you want to use
timezone = 'America/Montreal'

@app.route('/', methods=['GET', 'POST'])
def create_game():
    # Récupère la liste des joueurs (pour alimenter le formulaire)
    players = get_players()
    if request.method == 'POST':
        # Récupération des données du formulaire pour un match 1v1
        player1_name = request.form['player1_name']
        print(f"player1_name: {player1_name}")
        
        player2_name = request.form['player2_name']
        print(f"player2_name: {player2_name}")
        
        # Ici, on récupère directement les scores individuels
        score1 = int(request.form['score1'])
        print(f"score1: {score1}")
        
        score2 = int(request.form['score2'])
        print(f"score2: {score2}")
        
        # Récupération de la date du match depuis le formulaire
        date = request.form['game_date']
        print(f"date: {date}")

        # Récupération de l'heure actuelle dans le fuseau horaire défini
        tz = pytz.timezone(timezone)
        now = datetime.now(tz).strftime('%H:%M:%S')
        
        # Conversion de la date en une chaîne avec l'heure actuelle
        date_str = datetime.strptime(date, '%Y-%m-%d').strftime(f'%Y-%m-%d {now}')

        # Traitement du match en mode 1v1 avec les deux joueurs et leurs scores
        process_game_data(player1_name, player2_name, score1, score2, date_str)
        
        return redirect('/thank_you')
       
    # Affichage du formulaire avec la liste des joueurs
    return render_template('create_game.html', players=players)


def get_last_match():
    """
    Récupère le dernier match enregistré en mode 1v1.
    Retourne un tuple contenant :
      - match_id,
      - la date du match,
      - le prénom du joueur gagnant,
      - le prénom du joueur perdant,
      - le score du gagnant,
      - le score du perdant.
    """
    # Utilisation d'un gestionnaire de contexte pour ouvrir et fermer automatiquement la connexion
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        # Requête SQL adaptée pour le mode 1v1 :
        # On joint la table Match avec la table Player pour récupérer le prénom
        # du joueur gagnant et du joueur perdant, en utilisant les colonnes
        # 'winning_player_id' et 'losing_player_id'
        cur.execute("""
            SELECT 
                m.match_id AS matchid,
                m.match_timestamp AS time,
                p1.first_name AS winner,
                p2.first_name AS loser,
                m.winning_score AS winner_score,
                m.losing_score AS loser_score
            FROM Match m
            JOIN Player p1 ON m.winning_player_id = p1.player_id
            JOIN Player p2 ON m.losing_player_id = p2.player_id
            ORDER BY m.match_id DESC
            LIMIT 1;
        """)
        last_match = cur.fetchone()  # Récupère le premier (et dernier) résultat
    return last_match

def get_winning_player(player1_score, player2_score):
    if player1_score > player2_score:
      return 1
    elif player2_score > player1_score:
      return 2
    else:
        return 0 

def get_player_ratings_before_after():
    """
    Récupère les classements (avant et après) pour le dernier match en mode 1v1.
    
    Pour chaque joueur du dernier match (gagnant et perdant), la requête retourne :
      - Le classement le plus récent (rating après, rn = 1)
      - Le classement précédent (rating avant, rn = 2)
      
    La requête utilise une expression WITH pour d'abord extraire le dernier match,
    puis pour obtenir les ratings des joueurs impliqués.
    """
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()
        cur.execute("""
            WITH last_match AS (
                SELECT 
                    m.match_id AS match_id,
                    m.match_timestamp AS match_time,
                    m.winning_player_id AS player1_id,
                    m.losing_player_id AS player2_id
                FROM Match m
                ORDER BY m.match_id DESC
                LIMIT 1
            ),
            player_ratings AS (
                SELECT 
                    pm.player_id, 
                    pr.rating, 
                    pr.player_rating_timestamp, 
                    ROW_NUMBER() OVER (PARTITION BY pm.player_id ORDER BY pr.player_rating_timestamp DESC) AS rn
                FROM PlayerRating pr
                INNER JOIN PlayerMatch pm ON pr.player_match_id = pm.player_match_id
                WHERE pm.player_id IN (
                    SELECT player1_id FROM last_match
                    UNION ALL
                    SELECT player2_id FROM last_match
                )
            )
            SELECT 
                p.player_id, 
                p.first_name, 
                pr_before.rating AS rating_before, 
                pr_after.rating AS rating_after
            FROM Player p
            LEFT JOIN player_ratings pr_before ON p.player_id = pr_before.player_id AND pr_before.rn = 2
            LEFT JOIN player_ratings pr_after ON p.player_id = pr_after.player_id AND pr_after.rn = 1
            WHERE p.player_id IN (
                SELECT player1_id FROM last_match
                UNION ALL
                SELECT player2_id FROM last_match
            )
            ORDER BY p.player_id;
        """)
        results = cur.fetchall()
    return results


import psycopg2

def delete_last_match():
    # Ouvre une connexion à la base et crée un curseur
    with psycopg2.connect(**DATABASE_CONFIG) as conn:
        cur = conn.cursor()

        # Démarre une transaction
        cur.execute("BEGIN;")

        # Récupère l'ID du dernier match enregistré
        cur.execute("SELECT match_id FROM \"match\" ORDER BY match_timestamp DESC LIMIT 1;")
        latest_match_id = cur.fetchone()[0]

        # Supprime les classements liés à ce match dans playerrating
        cur.execute(f"DELETE FROM playerrating WHERE player_match_id IN (SELECT player_match_id FROM playermatch WHERE match_id = {latest_match_id});")

        # Supprime les entrées correspondantes dans playermatch
        cur.execute(f"DELETE FROM playermatch WHERE match_id = {latest_match_id};")

        # Supprime le match lui-même
        cur.execute(f"DELETE FROM \"match\" WHERE match_id = {latest_match_id};")

        # Valide la transaction
        cur.execute("COMMIT;")



@app.route('/thank_you')
def thank_you():
    last_match = get_last_match()
    player_rat_bef_and_aft = get_player_ratings_before_after()
    message = request.args.get('message', None)
    return render_template('thank_you.html', last_match=last_match, player_rat_bef_and_aft=player_rat_bef_and_aft, message=message)



@app.route('/delete_last_match', methods=['POST'])
def delete_last_match_route():
    delete_last_match()
    return redirect(url_for('/'))


@app.route('/calculate_odds', methods=['GET', 'POST'])
def calculate_expected_score_route():
    print("calculate_expected_score_route called")
    if request.method == 'POST':
        # Récupération des données du formulaire pour un match 1v1
        player1_name = request.form['player1_name']
        player2_name = request.form['player2_name']
        print(f"Form data: player1_name={player1_name}, player2_name={player2_name}")

        # Appel de la fonction adaptée pour calculer les scores attendus en 1v1
        # La fonction calculate_expected_score prend désormais deux paramètres
        expected1, expected2, odd1, odd2 = calculate_expected_score(player1_name, player2_name)
        
        # Passage des valeurs calculées au template (formatage pour affichage en pourcentage et arrondi des cotes)
        return render_template('calculate_odds.html', players=get_players(), 
                               expected1="{:.2f}".format(expected1 * 100), 
                               expected2="{:.2f}".format(expected2 * 100), 
                               odd1=round(odd1, 2), 
                               odd2=round(odd2, 2),
                               player1_name=player1_name, player2_name=player2_name)
    else:
        # Affichage du formulaire pour saisir les détails du match
        players = get_players()
        print(f"Available players: {players}")
        return render_template('calculate_odds.html', players=players)

@app.route('/rating')
def rating():
    month = request.args.get('month', datetime.now().strftime('%m'))
    year = request.args.get('year', datetime.now().strftime('%Y'))
    player_ratings = get_latest_player_ratings(month=month, year=year)
    now = datetime.now()
    return render_template('rating.html', player_ratings=player_ratings, month=month, year=year, now=now)


@app.route('/match_list')
def match_list():
    month = request.args.get('month')
    if not month:
        month = request.args.get('month', datetime.now().strftime('%m'))
    matches = get_match_list(month=month)
    return render_template('match_list.html', matches=matches, month=month)

@app.route('/players')
def players_list_showed():
    players_list = get_players_detailed_list()
    print(players_list)  # Add this line to print the contents of players_list
    return render_template('players.html', players_list=players_list)


@app.route('/add_player', methods=['GET', 'POST'])
def add_player():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        conn = psycopg2.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT nextval('player_id_seq')")
        id_next_player = cursor.fetchone()[0]
        cursor.execute("INSERT INTO player (player_id, first_name, last_name) VALUES (%s, %s, %s)", (id_next_player, first_name, last_name))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('players_list_showed'))
    else:
        return render_template('add_player.html')

    
@app.route('/edit_player/<int:player_id>', methods=['GET', 'POST'])
def edit_player(player_id):
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        active = True if request.form.get('active') else False

        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE Player SET first_name = %s, last_name = %s, active = %s WHERE player_id = %s",
                            (first_name, last_name, active, player_id))
                conn.commit()

        return redirect(url_for('players_list_showed'))
    else:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT player_id, first_name, last_name, active FROM Player WHERE player_id = %s", (player_id,))
                player = cur.fetchone()

        if player:
            return render_template('edit_player.html', player_id=player[0], player=player[1:])
        else:
            abort(404)

@app.route('/delete_match', methods=['GET', 'POST'])
def delete_match():
    if request.method == 'POST':
        match_id = request.form['match_id']

        # Ouverture de la connexion à la base de données avec un gestionnaire de contexte
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                # Suppression des classements des joueurs liés à ce match
                cur.execute("""
                    DELETE FROM playerrating 
                    WHERE player_match_id IN (
                        SELECT player_match_id FROM playermatch WHERE match_id = %s
                    );
                """, (match_id,))
                
                # Suppression des correspondances dans playermatch pour ce match
                cur.execute("""
                    DELETE FROM playermatch WHERE match_id = %s;
                """, (match_id,))
                
                # Suppression du match lui-même de la table Match
                cur.execute("""
                    DELETE FROM "match" WHERE match_id = %s;
                """, (match_id,))
                
                # Valider la transaction
                conn.commit()

        # Redirection vers une page (ici 'add_player', à adapter selon ton besoin)
        return redirect(url_for('add_player'))
    else:
        # Affichage du formulaire de suppression si la méthode HTTP n'est pas POST
        return render_template('delete_match.html')



 
    
    
@app.route('/show_dash')
def rating_evolution():
    return render_template('rating_evolution.html')

@app.route('/do_more')
def do_more():
    return render_template('do_more.html')

def get_player_id_metrics(player_name):
    conn = psycopg2.connect(
        host=DATABASE_CONFIG['host'],
        database=DATABASE_CONFIG['database'],
        user=DATABASE_CONFIG['user'],
        password=DATABASE_CONFIG['password']
    )
    cur = conn.cursor()

    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player_name,))
    player_id = cur.fetchone()[0]

    cur.close()
    conn.close()

    return player_id


@app.route('/metrics', methods=['GET', 'POST'])
def player_stats_route():
    """
    Affiche les statistiques d'un joueur en mode 1v1.
    Pour un joueur donné, on récupère :
      - le nombre total de matchs joués,
      - le nombre de victoires,
      - le nombre de défaites,
      - le score moyen par match,
      - l'opposant le plus fréquent (et son win rate contre le joueur).
    """
    if request.method == 'POST':
        player_name = request.form['player_name']
        # Récupère l'ID du joueur (la fonction get_player_id_metrics doit être adaptée pour le mode 1v1)
        player_id = get_player_id_metrics(player_name)
        
        # Connexion à la base de données
        conn = psycopg2.connect(
            host=DATABASE_CONFIG['host'],
            database=DATABASE_CONFIG['database'],
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password']
        )
        cur = conn.cursor()
        
        # Total des matchs joués par le joueur
        cur.execute("SELECT COUNT(*) FROM playermatch WHERE player_id = %s", (player_id,))
        total_games = cur.fetchone()[0]
        
        # Total des victoires (match où le joueur est gagnant)
        cur.execute("SELECT COUNT(*) FROM match WHERE winning_player_id = %s", (player_id,))
        total_wins = cur.fetchone()[0]
        
        # Total des défaites (match où le joueur est perdant)
        cur.execute("SELECT COUNT(*) FROM match WHERE losing_player_id = %s", (player_id,))
        total_losses = cur.fetchone()[0]
        
        # Calcul du score moyen par match pour le joueur
        # On prend le score du joueur selon s'il a gagné ou perdu
        cur.execute("""
            SELECT AVG(CASE 
                         WHEN winning_player_id = %s THEN winning_score 
                         WHEN losing_player_id = %s THEN losing_score 
                         END)
            FROM match
            WHERE %s IN (winning_player_id, losing_player_id)
        """, (player_id, player_id, player_id))
        avg_score = cur.fetchone()[0]
        
        # Récupérer l'opposant le plus fréquent (i.e. l'adversaire avec qui le joueur a le plus joué)
        # On détermine d'abord l'opposant pour chaque match du joueur, puis on compte la fréquence
        cur.execute("""
            SELECT opponent, COUNT(*) AS games_played
            FROM (
                SELECT CASE 
                    WHEN winning_player_id = %s THEN losing_player_id
                    WHEN losing_player_id = %s THEN winning_player_id
                END AS opponent
                FROM match
                WHERE %s IN (winning_player_id, losing_player_id)
            ) sub
            GROUP BY opponent
            ORDER BY games_played DESC
            LIMIT 1;
        """, (player_id, player_id, player_id))
        most_played_opponent_data = cur.fetchone()
        if most_played_opponent_data:
            opponent_id = most_played_opponent_data[0]
            games_with_opponent = most_played_opponent_data[1]
            # Récupération du nom de l'opposant
            cur.execute("SELECT first_name, last_name FROM player WHERE player_id = %s", (opponent_id,))
            opponent_info = cur.fetchone()
            if opponent_info:
                opponent_name = opponent_info[0] + " " + (opponent_info[1] if opponent_info[1] else "")
            else:
                opponent_name = "Unknown"
        else:
            opponent_name = None
            games_with_opponent = 0
        
        # Calcul du win rate contre cet opposant, si disponible
        if opponent_name:
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN winning_player_id = %s THEN 1 END) AS wins,
                    COUNT(*) AS total
                FROM match
                WHERE (winning_player_id = %s OR losing_player_id = %s)
                  AND ((winning_player_id = %s AND losing_player_id = %s) OR (winning_player_id = %s AND losing_player_id = %s))
            """, (player_id, player_id, player_id, player_id, opponent_id, opponent_id, player_id))
            result = cur.fetchone()
            if result and result[1] != 0:
                opponent_win_rate = round((result[0] * 100.0) / result[1], 2)
            else:
                opponent_win_rate = 0.0
        else:
            opponent_win_rate = None
        
        # Fermeture de la connexion à la base de données
        cur.close()
        conn.close()
        
        # Récupération de la liste complète des joueurs pour le template (fonction existante dans ton code)\n        players = get_players_full_list()
        
        return render_template('metrics.html',
                               players=players,
                               player_name=player_name,
                               total_games=total_games,
                               total_wins=total_wins,
                               total_losses=total_losses,
                               avg_score=avg_score,
                               most_played_opponent=opponent_name,
                               games_with_opponent=games_with_opponent,
                               opponent_win_rate=opponent_win_rate)
    else:
        # En méthode GET, afficher le formulaire pour sélectionner un joueur
        players = get_players_full_list()
        print(f"Available players: {players}")
        return render_template('metrics.html', players=players)




#DASH START HERE#

dash_app = dash.Dash(__name__, server=app, external_stylesheets=[dbc.themes.BOOTSTRAP, '/static/style.css'])

fontFormat = dict(family="Segoe UI, Roboto, Helvetica Neue, Helvetica, Microsoft YaHei, Meiryo, Meiryo UI, Arial Unicode MS, sans-serif",
                  size=18,)

engine = create_engine(
    f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@"
    f"{DATABASE_CONFIG['host']}/{DATABASE_CONFIG['database']}"
)

dash_app.layout = dbc.Container([
    html.H1('Rating Evolution'),
    html.Link(href='/static/style.css', rel='stylesheet'),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='player-dropdown',
                options=[{'label': player, 'value': player} for player in get_players_full_list()],
                value=['Matthieu', 'Lazare'],
                multi=True
            ),
            width={"size": 10, "offset": 1},
            lg={"size": 6, "offset": 3},
            md={"size": 8, "offset": 2},
            sm={"size": 12, "offset": 0},
        )
    ], style={"margin-top": "20px"}),
    dbc.Row([
        dbc.Col(
            dcc.Graph(id='rating-graph'),
            width={"size": 12, "offset": 0},
            lg={"size": 12, "offset": 0},
            md={"size": 12, "offset": 0},
            sm={"size": 12, "offset": 0}
        )
    ], className="graph-row",style={"margin-top": "20px"})
,
    html.Div([
    dbc.Row([
        dbc.Col(
            html.Div([
                html.H2('Explore more options'),
                html.P('Make the most of your game time with this all-in-one platform. Calculate your odds, compare your ranking, and upload your game results quickly and easily.')
            ]),
            width={"size": 10, "offset": 1},
            lg={"size": 6, "offset": 3},
            md={"size": 8, "offset": 2},
            sm={"size": 12, "offset": 0},
        )
    ], className="do-more", style={"margin-top": "20px"}),
    dbc.Row([
        dbc.Col(
            html.Div([
                 html.Div([
                                html.A('Upload game', href='/',
                                       className='action action1'),
                                html.A('Calculate odds', href='/calculate_odds',
                                       className='action action2'),
                                html.A('Ranking', href='/rating',
                                       className='action action3'),
                                html.A('Match history', href='/match_list',
                                       className='action action4'),
                                # Add two more options
                                html.A('Rating evolution', href='/rating_evolution',
                                       className='action action5'),
                                # Add Rating Evolution option
                                html.A('Player metrics', href='/metrics',
                                       className='action action7'),
                            ], className='action-grid')
                        ]),
                        width=12
        )
    ], style={"margin-top": "20px"}),
    
], style={"margin-left": "0px","background-color": "#EEF0F9"})
])




@dash_app.callback(
    Output('rating-graph', 'figure'),
    Input('player-dropdown', 'value')
)

def update_rating_graph(players):
    fig = go.Figure()
    for player in players:
        query = f"""SELECT
        DISTINCT ON (DATE_TRUNC('day', m.match_timestamp))
        DATE_TRUNC('day', m.match_timestamp) AS day_start,
            CASE WHEN p.first_name = '{player}' THEN pr.rating ELSE NULL END AS rating
        FROM PlayerMatch pm
        JOIN Player p ON pm.player_id = p.player_id
        JOIN PlayerRating pr ON pm.player_match_id = pr.player_match_id
        JOIN Match m ON pm.match_id = m.match_id
        WHERE p.first_name = '{player}'
        ORDER BY DATE_TRUNC('day', m.match_timestamp) DESC, m.match_timestamp DESC
                        """

        data = pd.read_sql(query, engine)
        fig.add_trace(go.Scatter(x=data['day_start'], y=data['rating'], name=player, line=dict(shape='spline')))
    fig.update_xaxes(title_text='')
    fig.update_yaxes(title_text='')
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    fig.update_layout(font=fontFormat)
    fig.update_yaxes(ticksuffix = "  ")
    fig.update_layout(legend_orientation="h")
    
    # Set different width and height values based on screen size
    fig.update_layout(
    autosize=True,
    margin= dict(l=0, r=0, t=30, b=10),
    paper_bgcolor="white",
    plot_bgcolor="white",
    dragmode='zoom',
    uirevision='constant',
    xaxis=dict(
        fixedrange=False,
        showgrid=True,  # Show the grid along the X axis
        gridcolor='lightgray',  # Set the grid color along the X axis
        gridwidth=0.5,  # Set the grid width along the X axis
    ),
    yaxis=dict(
        fixedrange=True,
        showgrid=True,  # Show the grid along the Y axis
        gridcolor='lightgray',  # Set the grid color along the Y axis
        gridwidth=0.5,  # Set the grid width along the Y axis
    ),
    legend=dict(
        orientation="h",  # Set the legend orientation to horizontal
        xanchor="center",  # Anchor the legend horizontally at the center
        x=0.5,  # Position the legend at the center along the X axis
        yanchor="bottom",  # Anchor the legend vertically at the bottom
        y=-0.22,  # Position the legend slightly below the bottom along the Y axis
    ),
)

    
    fig.update_layout(
    legend=dict(
        font=dict(family='Segoe UI, Roboto, Helvetica Neue, Helvetica, Microsoft YaHei, Meiryo, Meiryo UI, Arial Unicode MS, sans-serif', size=12),
        # other legend properties...
    ),
    xaxis=dict(
        tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Helvetica, Microsoft YaHei, Meiryo, Meiryo UI, Arial Unicode MS, sans-serif', size=12),

    ),
    yaxis=dict(
        tickfont=dict(family='Segoe UI, Roboto, Helvetica Neue, Helvetica, Microsoft YaHei, Meiryo, Meiryo UI, Arial Unicode MS, sans-serif', size=12),

    ),
    # other layout properties...
)

    
    return fig

if __name__ == '__main__':
    app.static_folder = 'static'
    app.run(host='0.0.0.0', port=8082, debug=True)