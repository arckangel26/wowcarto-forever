# WoWCarto Forever — guide Windows

## Installer et démarrer

1. Ouvrir `WoWCartoForever-Setup.exe`, puis suivre les étapes en français.
2. Garder le dossier proposé. Le programme s'installe pour le compte Windows courant, sans demander de droits administrateur.
3. Garder « Créer un raccourci sur le Bureau » si souhaité, puis cliquer sur « Installer ».
4. À la dernière étape, garder « Lancer WoWCarto Forever » et cliquer sur « Terminer ».

Le client Windows 64 bits `0.9.1` fonctionne sans installer Python et sans commande à saisir.
Au premier démarrage, sélectionner le fichier `Wow.exe` du jeu Forever, puis choisir
la qualité SD ou HD et attendre la génération locale. Sélectionner ensuite la base
française ou anglaise : elle est téléchargée et vérifiée avant ouverture en consultation.
Une connexion est nécessaire pour ce premier téléchargement ; les données restent locales
pour les démarrages suivants. Les positions historiques ne sont pas toutes vérifiées
dans Forever.
Après l'installation, le programme s'ouvre depuis son raccourci du Bureau ou le menu Démarrer.

## Retrouver les commandes du 1.20

Les quatre boutons de droite et `F1` à `F4` affichent les panneaux **Régions**, **Liste Master**, **Résultats** et **Informations** dans la fenêtre principale. La liste Master charge les annotations par lots de 500 pour rester réactive.

`Ctrl+F` ouvre une nouvelle recherche, `Ctrl+G` reprend ses paramètres et `Ctrl+T` limite à la région affichée. Les critères se cochent dans l’arbre et restent sélectionnés lorsqu’on filtre la liste. L’historique conserve le texte et les paramètres ; « Options » développe ou réduit les filtres.

`H` ouvre l’aide clavier, `A` masque les annotations, `L` leurs légendes, `S` assombrit la carte, `F` recentre l’annotation sélectionnée et `Z` revient au zoom 1:1. Ces lettres ne commandent pas la carte lorsqu’on écrit dans un champ. `Échap` quitte une sélection.

Les icônes de barre d’outils, les catégories, le drapeau de base et l’icône Windows reprennent les ressources locales d’origine. La taille des marqueurs reste « Confort ×2 » par défaut ; Préférences permet aussi « Compact ×1 ». Aucun cercle jaune n’est ajouté aux annotations sélectionnées. L’onglet Légendes des préférences personnalise localement la couleur et la police de chaque catégorie ; les couleurs de difficulté des mobs restent prioritaires tant que cette option est cochée.

L’éditeur reprend les trois colonnes du 1.20 : catégories à gauche, nom/niveaux/commentaires au centre, propriétés à droite. Les deux vues de commentaire conservent le même texte brut. `Ctrl+Entrée` enregistre ; Entrée ajoute une ligne dans le commentaire.

Les catégories apparaissent progressivement au zoom selon les seuils 1.20 ; les légendes suivent leurs propres seuils. Le bouton Chemins affiche les vecteurs et surfaces natifs reconnus. En mode édition 1.20, le clic droit permet aussi de créer un chemin personnel : clics pour ajouter des points, double-clic ou Échap pour terminer, clic droit pour annuler le dernier point ou régler l’opacité. Ces chemins restent dans le profil et dans ses sauvegardes.

La fenêtre Cartes vérifie les ressources préparées et permet de sélectionner un autre dossier compatible. Elle n’extrait pas les archives MPQ du jeu. La fenêtre Mise à jour utilise le service HTTPS actuel ; les anciens transports HTTP/FTP/MAPI ne sont pas réactivés. Le calcul historique « lvl Wizard », les commandes opaques Bridge et les seuils exacts de visibilité du 1.20 ne sont pas certifiés ; les aides correspondantes conservent les données et indiquent leur fonction réelle.

Les mises à jour conservent les annotations et les préférences personnelles.
La désinstallation retire le programme et laisse ces données disponibles pour une réinstallation.
Les installations originales de WoWCartographe restent séparées.

## Utiliser les cartes

Le menu en haut à gauche (Legacy), ou « Menu / données / sauvegardes » (Modern),
sépare **Interface : Legacy / Modern** de **Jeu de données : 1.20 / Legacy / Forever**.
Les deux interfaces utilisent les mêmes cartes, recherches et annotations.

Choisir une région dans la liste, glisser la carte pour se déplacer, utiliser la
molette pour zoomer et la miniature pour recentrer. `Ctrl+F` ouvre la recherche :
texte, catégories, tags, continents, régions, niveaux et ajouts locaux. Le bouton
« Options » développe, réduit ou réinitialise les filtres. Les résultats sont
paginés par 500. Sélectionner un résultat centre la carte ; « Détails » affiche sa
fiche. « Catégories affichées » filtre les icônes, sans modifier les bases.

Pour ajouter une annotation, choisir les données **1.20**, activer **Mode édition**
et sélectionner la même langue de base dans **Base autorisée pour l'édition**.
Faire un clic droit sur la carte, puis « Ajouter une annotation », ou `Ctrl+N`
pour le centre de la carte. Le clic droit sur un point permet sa modification.
Les annotations personnelles peuvent être masquées puis restaurées. Les bases
originales restent immuables ; les modifications sont des surcharges SQLite.
Les données Legacy candidates sont en lecture seule. Forever affiche des
annotations historiques recalées ; il ne permet pas de créer des coordonnées
Forever prétendument validées.

`Ctrl+,` ouvre les préférences. Le changement d'interface conserve la vue,
la sélection, la recherche et les fenêtres ouvertes. La fermeture enregistre
le cadrage, les filtres de carte et les préférences pour le prochain lancement.
Le changement de jeu de données réinitialise la navigation et les résultats,
car les identifiants et coordonnées diffèrent.

Les commandes d'export et import JSON conservent l'historique des annotations.
L'import fusionne les données, ignore les copies identiques et refuse les
conflits sans écrasement. « Sauvegarder le profil » crée un `.wcfbackup` avec
annotations, historique et préférences, protégés par SHA-256. La restauration
fusionne les notes ; ses préférences s'appliquent au prochain lancement. Fermer
les autres fenêtres du client avant une restauration. Une sauvegarde SQLite
précède l'import dans un profil non vide. Choisir un nom de fichier nouveau
pour les exports et sauvegardes.

Toutes les fonctions locales fonctionnent sans service. `--offline` désactive
les commandes réseau ; les caches déjà vérifiés restent consultables. Le partage
est une action explicite, avec confirmation dans le client. Une panne du service
ne supprime pas les annotations locales. Les limites géographiques et la
provenance sont visibles dans les informations de carte et les détails.

L'installateur met à jour les fichiers applicatifs et laisse le profil à son
emplacement stable. La désinstallation conserve ce profil. Les archives
originales, les autres installations et les sauvegardes ne sont pas supprimées.
Le paquet créé avec `--local-data` contient des ressources propriétaires : usage
local privé uniquement, aucune autorisation de redistribution n'est établie.
Une construction sans données génère les cartes depuis le jeu local et télécharge la
base historique 1.20 pendant le premier lancement.
Les deux bandes d'icônes de l'interface 1.20 sont incluses ; leurs conditions de
redistribution restent à vérifier auprès des titulaires des droits.

Les données personnelles sont conservées dans `%LOCALAPPDATA%\WoWCartoForeverClone`,
indépendamment du dossier du programme. Le nom historique de ce dossier reste inchangé
afin de retrouver les profils déjà créés. Pour conserver une copie transportable,
utiliser « Sauvegarder le profil » dans l'application.

## Reconstruction

Dans un environnement Windows Python 3.11 isolé, installer
`requirements-client-windows.txt`, puis depuis la racine :

```powershell
python -m tools.build_clone_windows "C:\nouveau-dossier-de-build" --local-data "C:\donnees-preparees" --iscc "C:\Inno-Setup\ISCC.exe"
```

Omettre `--local-data` pour exclure les ressources propriétaires. Omettre
`--iscc` pour produire seulement le dossier exécutable. Le dossier de sortie
doit être nouveau. Le script vérifie bases et packs, conserve les empreintes
des sources et données, la commande de construction et les versions des
dépendances dans `delivery.json`. `sources-client.zip` fige les sources Python
utilisées, y compris les modifications non commitées. Une reconstruction
fonctionnelle est visée ; l'identité binaire bit à bit n'est pas garantie.

La version de l'application pilote aussi la version de l'installateur et les propriétés
de l'exécutable Windows. Pour une construction privée avec données, l'icône originale
locale existante est intégrée si elle est disponible. `--app-icon "C:\icone.ico"`
permet de sélectionner explicitement une autre icône existante. Son empreinte est
conservée dans le manifeste ; cela n'accorde aucun droit de redistribution.

Pour une recette d'installation, `/ValidationSandbox=1` utilise une inscription de
désinstallation, un raccourci Démarrer et un profil de test distincts. Le profil de test
est `%LOCALAPPDATA%\WoWCartoForever-Test`. Aucun raccourci de Bureau normal n'est créé
par ce mode. Une ancienne installation reconnue par son identifiant conserve son
dossier lors de la mise à jour ; une nouvelle installation normale propose
`%LOCALAPPDATA%\Programs\WoWCartoForever`.

Lors d'une reconstruction avec les mêmes ressources, `--verified-data
"C:\ancien-build\delivery.json"` permet de réutiliser leur validation de
décodage. Chaque fichier est de nouveau haché ; la réutilisation est refusée
si une seule empreinte diffère. Le manifeste conserve l'empreinte du précédent
manifeste. Ce cache concerne les ressources, jamais les sources ou l'exécutable.
