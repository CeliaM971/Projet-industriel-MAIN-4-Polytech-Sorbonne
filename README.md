
Le fichier requirements.txt ajoute le dans backend et sur ton terminal execute :
 pip install -r requirements.txt 
 
 pour installer tous les dépendances


uvicorn user_database:app --reload --host 0.0.0.0 --port 8000

lien API Navigateur :
    http://localhost:8000/docs


# Guide de démarrage complet de l'application

Application mobile Flutter avec backend FastAPI + MariaDB.

---

## Prérequis

- Flutter SDK installé et configuré ([flutter.dev](https://flutter.dev/docs/get-started/install))
- Python 3.10+
- MariaDB Server
- Un émulateur Android/iOS ou un appareil physique connecté

---

## Étape 1 — Cloner le projet

```bash
git clone <https://gitlabsu.sorbonne-universite.fr/projet-industriel-main4/projet-industriel>
```

---

## Étape 2 — Configuration du backend Python

### 2.1 Créer et activer un environnement virtuel

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

```

### 2.2 Installer les dépendances Python

```bash
pip install -r requirements.txt
```

> Le fichier `requirements.txt` est présent dans le lib/backend/



---

## Étape 3 — Configuration de MariaDB

### 3.1 Démarrer MariaDB

```bash
# Démarrer le service
sudo systemctl start mariadb

# Vérifier que le service tourne
sudo systemctl status mariadb

# (Optionnel) Démarrage automatique au boot
sudo systemctl enable mariadb
```

### 3.2 Créer l'utilisateur et la base de données

> ⚠️ À ne faire qu'une seule fois.

```bash
sudo mariadb -e "
CREATE DATABASE IF NOT EXISTS typannot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'typannot'@'localhost' IDENTIFIED BY 'motdepasse';
CREATE USER IF NOT EXISTS 'typannot'@'127.0.0.1' IDENTIFIED BY 'motdepasse';
GRANT ALL PRIVILEGES ON typannot_db.* TO 'typannot'@'localhost';
GRANT ALL PRIVILEGES ON typannot_db.* TO 'typannot'@'127.0.0.1';
FLUSH PRIVILEGES;
"
```

> Sur Linux, `sudo mariadb` ne demande pas de mot de passe. Sur certains systèmes, ajoutez `-p` si nécessaire.

### 3.3 Les tables sont créées automatiquement

Au premier lancement du backend, SQLModel crée automatiquement toutes les tables via `SQLModel.metadata.create_all(engine)`. Aucune migration manuelle n'est nécessaire.

---

## Étape 4 — Lancer le backend FastAPI depuis lib

### Configuration de l'adresse IP

Avant de lancer le backend, renseignez votre adresse IP locale dans `lib/config.json` :

```json
{
  "server_ip": "192.168.1.100",
  "server_port": 8000
}
```

Pour trouver votre adresse IP locale :

- **Linux** : `hostname -I` → cherchez une adresse du type `192.168.x.x`
- **Mac** : `ipconfig getifaddr en0` (Wi-Fi) ou `ipconfig getifaddr en1` (Ethernet)

Sur **émulateur Android**, utilisez `10.0.2.2` à la place de votre IP locale :
```json
{
  "server_ip": "10.0.2.2",
  "server_port": 8000
}
```
> `10.0.2.2` est l'adresse spéciale qui redirige vers `localhost` de votre machine hôte dans l'émulateur Android.

> Attention, sur un **appareil physique**, utilisez votre adresse IP locale (ex: `192.168.x.x`) et assurez-vous que le téléphone et la machine sont sur le **même réseau Wi-Fi**.

### Lancement du backend FastAPI

```bash
uvicorn backend.main:app --reload
```

Le serveur démarre sur `http://127.0.0.1:8000`.

Pour vérifier que tout fonctionne, ouvrez dans votre navigateur :

- Documentation interactive : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check : [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

> ⚠️ Le backend doit rester lancé pendant toute la durée d'utilisation de l'application.

---

## Étape 5 — Configuration de Flutter

Ces commandes sont à réaliser dans le dossier appli_typannot:

### 5.1 Vérifier l'installation Flutter

```bash
flutter doctor
```

Assurez-vous que tous les items essentiels sont cochés (Android toolchain, émulateur ou device connecté).

### 5.2 Effacer les dépendances

```bash
flutter clean
```

### 5.3 Installer les dépendances Flutter

```bash
flutter pub get
```

### 5.4 Configurer l'URL du backend

Vérifiez que l'URL de l'API dans le code Flutter pointe bien vers votre backend :

- **Émulateur Android** → utiliser `http://10.0.2.2:8000`
- **Appareil physique** → utiliser l'IP locale de votre machine (ex: `http://192.168.1.XX:8000`)
- **iOS Simulator / macOS** → utiliser `http://127.0.0.1:8000`

---

## Étape 6 — Lancer l'application Flutter

### Sur émulateur

```bash
# Lister les émulateurs disponibles
flutter emulators

# Lancer un émulateur
flutter emulators --launch <emulator_id>

# Lancer l'application
flutter run
```

### Sur appareil physique

- Sur Iphone vérifiez que le mode développeur est activé

Connectez votre téléphone en USB avec le débogage USB activé, puis :

```bash
flutter devices        # vérifier que l'appareil est détecté
flutter run
```

### En mode release (performances optimales)

```bash
flutter run --release
```

---

## Résumé — ordre de lancement

À chaque session de développement, lancer dans cet ordre :

```bash
# 1. Activer l'environnement virtuel Python
source venv/bin/activate

# 2. Démarrer MariaDB (si pas déjà actif)
sudo systemctl start mariadb

# 3. Lancer le backend
uvicorn backend.main:app --reload

# 4. Dans un autre terminal, lancer Flutter
flutter run
```

---


## Dépannage fréquent

**`ModuleNotFoundError: No module named 'pymysql'`**
→ Relancer `pip install -r requirements.txt` dans l'environnement virtuel activé.

**`Access denied for user 'typannot'`**
→ Vérifier que l'utilisateur MariaDB a bien été créé (Étape 3.2).

**`flutter pub get` échoue**
→ Vérifier la version du SDK Flutter avec `flutter --version` (requis : `^3.9.2`).

**L'app ne peut pas joindre le backend**
→ Vérifier l'URL de l'API selon votre environnement (Étape 5.3).

**`Connection refused` sur le port 8000**
→ S'assurer que le serveur uvicorn est bien lancé (Étape 4).