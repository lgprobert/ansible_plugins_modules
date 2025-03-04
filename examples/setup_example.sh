#!/bin/bash

DB_FILE="inventory.db"
BACKUP_FILE="inventory_example.sql"

if ! command -v sqlite3 &> /dev/null; then
    echo "Error: sqlite3 tool not found. Please install sqlite3 and try again."
    exit 1
fi

if [ -f "$DB_FILE" ]; then
    echo "Rename existing database file: $DB_FILE"
    mv "$DB_FILE" "$DB_FILE.old"
fi

if ! [ -f "$BACKUP_FILE" ]; then
    echo "Error: inventory backup file $BACKUP_FILE not found."
    exit 1
fi

echo "Restoring database from backup file: $BACKUP_FILE"
sqlite3 "$DB_FILE" < "$BACKUP_FILE"

echo "Ansible sqlite based inventory sample setup complete."
