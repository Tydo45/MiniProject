CREATE USER auth_service WITH PASSWORD 'auth_pass';
CREATE DATABASE auth_db OWNER auth_service;

CREATE USER lobby_service WITH PASSWORD 'lobby_pass';
CREATE DATABASE lobby_db OWNER lobby_service;

CREATE USER chess_service WITH PASSWORD 'chess_pass';
CREATE DATABASE chess_db OWNER chess_service;