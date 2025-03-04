from urllib.parse import urlparse

ENV = "prod"  # Change to "dev" if using local database

if ENV == 'dev':
    DATABASE_CONFIG = {
        'host': "localhost",
        'database': "babyfootgph",
        'user': "arthurcare",
        'password': "Hockey12"}
    
else: 
    uri = "postgresql://fbf_gph_user:lVKWHbC3sG6P26wUOap2j0l9jREDzIs8@dpg-cv3453dumphs73a188mg-a.oregon-postgres.render.com/fbf_gph"
    parsed_uri = urlparse(uri)

    DATABASE_CONFIG = {
        'host': parsed_uri.hostname,
        'database': parsed_uri.path[1:],  # Remove leading "/"
        'user': parsed_uri.username,
        'password': parsed_uri.password,
        'port': parsed_uri.port
    }
