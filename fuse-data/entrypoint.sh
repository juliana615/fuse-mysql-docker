#!/usr/bin/env sh

set -e  # Beendet das Skript bei Fehlern

# Verzeichnis erstellen, falls es nicht existiert
if [ ! -d "/mnt/vfs" ]; then
  mkdir -p /mnt/vfs
fi

echo "Warte auf MySQL-Datenbank..."

# Warte, bis MySQL verf�gbar ist
until mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "SELECT 1;" > /dev/null 2>&1; do
  echo "MySQL ist noch nicht verf�gbar, erneut versuchen..."
  sleep 3
done

echo "MySQL ist verf�gbar. Starte das FUSE-Dateisystem."

# Starte das FUSE-Dateisystem
if python3 /app/mysql-fuse-filesystem.py /mnt/vfs -o allow_other; then
  echo "FUSE-Dateisystem erfolgreich gestartet."
else
  echo "Fehler beim Starten des FUSE-Dateisystems!" >&2
  exit 1
fi
