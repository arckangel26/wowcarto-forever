# Schéma communautaire initial

> Actualisation du 5 novembre 2026 : le service public est en schéma 5 et ouvert.
> Les corrections historiques FR/EN sont liées aux identifiants et empreintes
> des sources. Les ajouts sont distribués par pages avec contrôle de génération ;
> les anciens clients utilisant `community_snapshot` restent limités à 2 000
> lignes et doivent être mis à jour. Les sections suivantes décrivent aussi des
> étapes historiques qui ne constituent plus l'état actuel du déploiement.

`mysql/001_initial.sql` crée cinq tables InnoDB, sans compte ni contribution.
Sélectionner la base cible dans phpMyAdmin avant exécution. Le script ne contient
aucune suppression et échoue si une table existe déjà. Les instructions DDL MySQL
ne sont pas transactionnelles : une erreur exige d'inspecter les tables créées
avant de reprendre, sans relancer aveuglément le script.

- `wcf_schema_versions` : version installée.
- `wcf_members` : identité et hachage de mot de passe ; comptes désactivés par défaut.
- `wcf_imports` : fichier natif original et SHA-256 binaire, provenance par membre.
- `wcf_annotations` : lignes brutes et ordre, doublons conservés, validation en attente.
- `wcf_moderation_events` : décisions et auteur de la modération.

La déduplication s'effectue par membre et empreinte du fichier. Un import complet
doit être atomique : fichier et toutes ses lignes dans la même transaction. Le
service devra vérifier les limites, le format natif, la concordance du nombre de
lignes et du SHA-256, ainsi que les droits et transitions de modération. MySQL 5.7
ne permet pas de confier ces règles à des contraintes CHECK effectives.

Le journal et l'état de modération devront être écrits dans la même transaction.
Les clés étrangères empêchent les suppressions en cascade involontaires. Aucun
repère de coordonnées, encodage textuel ou identifiant d'entité non établi n'est
inventé. Les données natives sont des BLOB, sans conversion Unicode implicite.
MEDIUMBLOB impose une limite de 16 777 215 octets par valeur ; l'application devra
appliquer une limite inférieure compatible avec PHP et max_allowed_packet.

Le schéma seul ne fournit pas un export natif ou la synchronisation du client
1.20. Aucun compte administrateur ni mot de passe par défaut n'est créé. Une clé
étrangère ne prouve pas qu'un membre est modérateur.

## Validation chez Free

Le 28 octobre 2026, le schéma a été installé dans la base vide cible. Le script
`mysql/verify_transaction.sql` a vérifié deux lignes identiques à deux positions
distinctes, leur état `pending`, puis l'annulation complète des écritures par
ROLLBACK. Résultats : 2 / 2 / 1 / 2, puis 0 / 0 / 0 / 0. Les valeurs du fichier
de test sont des fixtures SQL, pas un fichier natif reconnu par le client.
Les droits Free ont refusé un contrôle supplémentaire via `information_schema` ;
le test conservé dans le dépôt n'en dépend pas.

## Service de réception PHP

`web/` contient un service PHP 8.5 sans dépendance externe et une interface pour
créer un compte, se connecter, envoyer un fichier d'ajouts et consulter ses
propres envois. Il s'agit d'une réception web ; le protocole du client 1.20 n'est
pas raccordé. Les annotations reçues commencent à l'état `pending`, sans diffusion native.

Installer `mysql/002_rate_limits.sql` après la version 1. Les deux lignes de
version sont conservées ; le maximum doit être 2. Les migrations ne doivent
jamais être relancées sans inspection préalable.

Sur le serveur, créer `web/private/config.php` à partir du modèle, avec la DSN
MySQL réelle, ses identifiants et un `rate_secret` aléatoire de 64 caractères
hexadécimaux. Ne pas versionner ce fichier. Le déploiement Free préparé utilise
un fichier `private/sql.php` distinct, également exclu de Git, pour les trois
valeurs `dsn`, `username` et `password`. Ces fichiers et le répertoire de sessions
ne doivent jamais être écrasés lors d'une mise à jour du code.

Déployer d'abord avec `public_open=false` et `registration_open=false`. Le serveur
doit fournir HTTPS et autoriser l'écriture dans `private/sessions`. Vérifier
`api.php?action=health`, puis `bootstrap`, et le refus HTTP 403 de `private/`,
de ses configurations et des fichiers de session. Le diagnostic health indique
uniquement l'étape et le code numérique du pilote en cas d'échec, jamais le
message SQL, les identifiants, la DSN ou le mot de passe. L'accès HTTPS est
obligatoire ; l'application ne fait pas confiance à un en-tête de proxy fourni
par le client.

L'ouverture réelle nécessite de passer explicitement les deux indicateurs à
`true`. Un compte créé via l'inscription est un membre actif, jamais un
administrateur. Aucun compte de démarrage n'est fourni. Les mots de passe sont
hachés avec bcrypt, coût 12 ; ils doivent contenir 12 à 72 octets. Le premier
compte humain doit être créé directement par son propriétaire, sans partager
le mot de passe avec l'agent.

Les sessions utilisent un cookie HttpOnly, SameSite Strict, Secure en HTTPS,
limité au chemin de l'application, avec renouvellement à la connexion, jeton
CSRF et expiration après 30 minutes d'inactivité ou 8 heures au total. Les
réglages suivent le [manuel PHP](https://www.php.net/manual/en/session.security.ini.php).
Les comptes désactivés sont refusés à chaque requête authentifiée.

Limites : 10 connexions par IP et par identifiant sur 15 minutes, 3 inscriptions
par IP/heure, 10 envois par membre sur 10 minutes, 100 fichiers ou 50 Mio par
membre. Seuls des HMAC des clés de limitation sont conservés ; les compteurs
inactifs depuis plus de 24 heures sont purgés de manière opportuniste. Les
limites ne remplacent pas une protection globale du serveur par l'hébergeur.

Un fichier est limité au minimum de 8 Mio, des limites PHP et de
`max_allowed_packet` moins une marge, avec un maximum de 2 000 annotations.
Le parseur refuse les versions inconnues, octets nuls et lignes de plus de
64 Kio. Cette lecture du format observé n'est pas une validation sémantique de
tous ses champs ni une conversion de coordonnées. Les noms des fichiers ne sont
pas utilisés pour écrire dans le système de fichiers du serveur.

## Modération expérimentale en local

Le code de cette branche ajoute le suivi des états pour les membres et une liste de décisions de modération aux
rôles `moderator` et `admin` actifs. Les membres ordinaires n'y ont pas accès.
Une décision accepte ou rejette une annotation en attente ; le refus exige un
motif. La décision et l'événement associé sont enregistrés dans la même
transaction, et une seconde décision sur une annotation déjà traitée est
refusée. La révision d'une décision et la création d'un premier modérateur ne
sont pas encore implémentées. Aucun compte ou rôle n'est créé automatiquement.

La liste de modération renvoie au plus cinq annotations par page avec navigation
dans les deux sens ; les requêtes de suivi sont limitées aux 100 derniers envois
du membre connecté. Cela borne la quantité de données affichées à la fois ; aucun
gain de mémoire ou de fluidité du client Windows original n’a été mesuré.

Les données brutes restent inchangées. L'interface affiche les champs connus et
essaie Windows-1252 pour le texte ; cette lecture peut être incorrecte pour une
autre page de code. Les positions sont des valeurs natives sans conversion
universelle. Les annotations acceptées ne sont ni publiées ni exportées vers
WoWCartographe : le format de mise à jour reste à établir. Le code n'a pas été
déployé sur Free et l'accès reste bloqué si `public_open=false`.

## Nouveau choix produit : communauté sans compte

Le 29 octobre, le propriétaire a demandé une contribution et une correction
libres, sans création de compte ni validation préalable. Les sections historiques
de modération ci-dessous décrivent l'ancien parcours et ne représentent plus le
comportement cible des contributeurs.

La migration additive `mysql/003_community.sql` prépare des imports anonymes,
des annotations et leur historique de révisions. Elle ne supprime pas les
anciennes tables et n'est pas déployée chez Free. Les nouveaux points d'API
`community_list`, `community_upload`, `community_edit` et `community_history` fonctionnent sans
compte lorsqu'un environnement de test est explicitement ouvert et en schéma 3.
Ils conservent les octets, l'ordre et les doublons ; les corrections deviennent
immédiatement visibles dans cette API. Une version périmée reçoit HTTP 409.
La route de recherche `community_candidate` prépare, pour une seule source,
un fichier contenant ses révisions courantes et vérifie l'intégrité de la source
et de son historique. Elle préserve les en-têtes, l'ordre, les doublons et les
séparateurs. Sa réponse indique `native_update=false` : elle n'est ni signée,
ni une synchronisation sécurisée ni un regroupement des différentes sources.

La fermeture `public_open=false` bloque toujours lecture et écriture de ces
routes. Les écritures exigent un jeton CSRF ; HTTPS reste obligatoire en
configuration normale. Les limitations par IP et globales, un quota de stockage,
des quotas distincts pour les fichiers et l'historique, des requêtes préparées
et des transactions bornent certains abus. L'accès SQL
doit rester privé et limité aux seuls privilèges nécessaires. Ces mesures ne
permettent ni d'identifier un auteur anonyme, ni de garantir l'exactitude des
annotations ; elles ne remplacent pas des sauvegardes et une restauration.

Une interface web locale permet l'import, la correction et la restauration d'une
révision sans compte. L'envoi et la réception natifs restent à raccorder.
Une ligne mise à jour dans l'API n'est pas encore une mise à jour consommée par
WoWCartographe. Les tests présents utilisent HTTP local et SQLite jetable ; la
migration MySQL et la concurrence réelle doivent encore être vérifiées. Le
propriétaire a demandé l'ouverture publique ; elle reste à réaliser après une
vérification du déploiement et des garanties de sécurité de bout en bout.

## Ancien parcours : sélection privée et premier administrateur

`POST api.php?action=review_export` exige un modérateur actif et un jeton CSRF.
Il fournit jusqu'à 20 annotations acceptées par page, avec leurs octets bruts,
leur ordre, l'empreinte de la source et l'événement de décision. Le service
vérifie l'intégrité de chaque source et de chaque ligne. Le JSON privé est un
paquet de revue, non signé et explicitement marqué `native_update=false` ; il
ne constitue ni publication ni mise à jour native. Le service fermé bloque
également cette action.

Les imports d'un membre sont sérialisés avant le contrôle du quota et de
l'idempotence. Une session désactivée est invalidée ; les indicateurs de
fermeture doivent être des booléens PHP et non des chaînes. `Retry-After`
correspond à la durée restante de la fenêtre de limitation.

Pour préparer, sans connexion SQL, le premier administrateur :

```powershell
python -m tools.prepare_first_admin --php CHEMIN/php.exe --username IDENTIFIANT --output CHEMIN_PRIVE/nouveau-premier-admin.sql
```

Le propriétaire saisit localement le mot de passe sans écho ; le programme
produit un SQL privé contenant uniquement son hachage bcrypt. Après sauvegarde
et inspection de la base cible, le propriétaire l'exécute lui-même : un verrou
nommé protège l'opération, qui refuse de créer un compte si un administrateur
ou l'identifiant existe déjà. Vérifier `accounts_created=1` au premier passage
et 0 lors d'une répétition, puis le rôle et l'état du compte. Ne pas publier le
fichier SQL. Aucun compte humain n'a été créé pendant les tests locaux.

Les tests concurrents couvrent les répétitions, quotas et décisions simultanées
sur une base jetable. Les résultats MariaDB locaux ne remplacent pas MySQL 5.7.

## Tests exécutables

Avec PHP CLI et pdo_sqlite, `python -m unittest discover -s tests -p
test_hosting_http.py -v` lance un serveur HTTP réel sur loopback et une base
SQLite jetable. Sur Windows portable, définir `WCF_PHP_BIN` et
`WCF_PHP_EXT_DIR`. Les tests couvrent le service fermé, les refus CSRF et
d'accès, la connexion/déconnexion, la désactivation, les octets bruts, les
doublons, l'idempotence, l'isolation des membres, les rejets, la limitation et le
rollback après erreur injectée, les rôles et décisions de modération. Le routeur local simule le refus de `private/` :
seul un contrôle réel chez Free prouve l'application des règles Apache.

La CI exécute également `tests/hosting_mysql.php` sur un MySQL 5.7 jetable. Ce
script refuse une DSN non locale, un nom de base hors préfixe `wcf_fixture_` ou
une base déjà remplie. Il vérifie les migrations, le hachage, les BLOB, les
doublons, l'idempotence, le rollback et la branche MySQL du limiteur. Cette CI
ne constitue pas un test de l'hébergement Free avec un vrai compte.

Le test `tests.test_hosting_browser` utilise Playwright et Chromium avec le
serveur PHP et SQLite jetables : il teste la connexion, la modération et
l'affichage sûr d'un texte ressemblant à du HTML. `WCF_CHROMIUM_BIN` permet de
choisir un Chromium local. Ces tests ne sont ni une validation du client Windows
natif, ni une mise en service sur Free.
