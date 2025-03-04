import psycopg2
from openpyxl import load_workbook
from config import DATABASE_CONFIG


# Connect to the database
conn = psycopg2.connect(
    host=DATABASE_CONFIG['host'],
    database=DATABASE_CONFIG['database'],
    user=DATABASE_CONFIG['user'],
    password=DATABASE_CONFIG['password']
)

# Create a cursor
cur = conn.cursor()

# Load the workbook
wb = load_workbook('data.xlsx')

# Select the active sheet
ws = wb.active

## Iterate through the rows of the sheet
for row in ws.rows:
  date = row[0].value
  player1_name = row[1].value
  player2_name = row[2].value
  player1_score = row[3].value
  player2_score = row[4].value


  # Check if the player name is not empty
  if player1_name:
    # Check if the player already exists in the Player table
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player1_name,))
    player1_id = cur.fetchone()
    if player1_id is None:
      # If the player does not exist, insert them into the players table with a unique id
      cur.execute("SELECT nextval('player_id_seq')")
      id = cur.fetchone()[0]
      cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (id, player1_name))
      player1_id = id
    else:
      # If the player already exists, retrieve their player_id
      player1_id = player1_id[0]
    # Print the first_name and id of the player
    print(f'Processing player1 {player1_name} with id {player1_id}')

  
# Check if the player2 first_name is not empty
  if player2_name:
    # Check if the player already exists in the Players table
    cur.execute("SELECT player_id FROM player WHERE first_name=%s", (player2_name,))
    player2_id = cur.fetchone()
    if player2_id is None:
      # If the player does not exist, insert them into the players table with a unique id
      cur.execute("SELECT nextval('player_id_seq')")
      id = cur.fetchone()[0]
      cur.execute("INSERT INTO player (player_id, first_name) VALUES (%s, %s)", (id, player2_name))
      player2_id = id
    else:
      # If the player already exists, retrieve their player_id
      player2_id = player2_id[0]
    # Print the first_name and player_id of the player
    print(f'Processing player2 {player2_name} with id {player2_id}')

# Commit the changes to the database    
conn.commit() 