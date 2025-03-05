from urllib.parse import urlparse

ENV = "prod"  # Change to "dev" if using local database

if ENV == 'dev':
    DATABASE_CONFIG = {
        'host': "localhost",
        'database': "*****",
        'user': "*****",
        'password': "*****"}
    
else: 
    uri = "*****"
    parsed_uri = urlparse(uri)

    DATABASE_CONFIG = {
        'host': parsed_uri.hostname,
        'database': parsed_uri.path[1:],  # Remove leading "/"
        'user': parsed_uri.username,
        'password': parsed_uri.password,
        'port': parsed_uri.port
    }
