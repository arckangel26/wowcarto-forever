# Revue et portage de l’interface 1.20 — version 0.9.1

La revue du 8 novembre 2026 couvre les 12 formulaires et 396 composants des ressources DFM du client local WoWCartographe 1.20, binaire SHA-256 `581d8940c6a5471184d7d8ce9e7cf01a2a5cf48ddabe427f8ff4b7483582d457`. Les captures historiques, les infobulles et les raccourcis fournis avec le client complètent ces ressources. L’exécutable original n’a pas été nécessaire pour modifier le client indépendant. Les preuves détaillées sont conservées dans `outputs/ui-finalization-20261108/reference-review/` et `path-research/`.

## Interface portée

| Formulaire ou zone native | Traitement dans la version 0.9.1 |
|---|---|
| Fenêtre principale TMAINFORM | Barres d’outils et indices d’icônes natifs ; panneaux dockés F1 Régions, F2 Master, F3 Résultats, F4 Informations ; déplacement, zoom, miniature, contexte et raccourcis documentés. |
| Éditeur TFORM2 | Trois colonnes : catégories avec glyphes, nom/niveaux/commentaires, propriétés hiérarchiques à cocher. Vues générale et avancée du même texte brut. Coordonnées, flags opaques et géométrie native conservés lors d’une surcharge locale. |
| Recherche TSEARCHFORM | Deux colonnes compactes 540×350, développement possible ; cases à cocher, résumé dynamique, filtrage sans perte de critères, historique complet des paramètres, Ctrl+F/Ctrl+G/Ctrl+T et résultats paginés. |
| Options TFORM3 | Onglets Général, Affichage, Légendes ; langue, base d’édition, thème, visibilité, qualité, niveau, taille des marqueurs, couleurs et polices locales ; sauvegarde/restauration du profil. |
| Langue et base TFORM1 | Rôles repris dans les menus, préférences et premier lancement guidé ; les données et la langue de l’interface restent distinctes. Le drapeau 20×13 vient de la section native de la base. |
| Informations TFORM5 | Onglets Infos et Crédits, version et emplacement du profil ; informations de base et d’annotation dans le panneau F4. |
| Cartes TFORM_GENERATE | Fenêtre dédiée aux ressources déjà préparées : vérification complète et choix d’un autre dossier compatible au prochain lancement. Le paquet privé inclut ses cartes. |
| Mise à jour TFORM_UPDATE | Onglets Connexion/Options ; réception communautaire et statut, mode hors ligne, service HTTPS actuel. Aucune publication automatique. |
| Envoi TMAIL_FIC | Commandes explicites de partage d’une annotation ou d’un fichier d’ajouts, avec les confirmations du client ; les anciens transports sont remplacés. |
| Chemins TFORM_WPOPTIONS | Affichage des commandes V_ et S_ reconnues ; création de chemins personnels, annulation du dernier point, fin par double-clic/Échap, réglage d’opacité et de visibilité en vue générale. Chemins personnels conservés dans les préférences et sauvegardes du profil. |
| Options de recherche TFORM7 | Fonctions établies exposées par les filtres et le menu Options ; les cases historiques dont la sémantique n’est pas prouvée ne sont pas inventées. |
| Saisie auxiliaire TFORM6 | Ressource revue ; déclenchement exact non établi, donc pas de fenêtre artificielle sans fonction. Les saisies utiles sont rattachées à leurs commandes effectives. |

## Icônes et dessin

Les boutons utilisent les bandes originales 16×16 normales/survolées. Les catégories UI utilisent leur bande 16×16 ; l’éditeur conserve les glyphes de carte 11×11. Les glyphes de carte s’affichent au facteur ×2 accepté pendant la session, avec un choix Compact ×1. Le champ coloré et le glyphe partagent la même grille de pixels. Aucun cercle jaune de sélection n’est ajouté. Le champ coloré est de 10 pixels pour un mob normal et de 14 pixels pour un élite, un unique ou un boss à l’échelle Confort. Les mobs communs portant le tag natif Élite utilisent le cadre natif des uniques ; cette distinction supplémentaire répond à la demande et ne prétend pas reproduire chaque détail du dessin Delphi.

Les six couleurs et les seuils de difficulté proviennent des routines natives ; le niveau effectif est celui de l’intervalle du mob le plus proche du niveau du personnage. Les polices et couleurs de catégorie proviennent des enregistrements natifs ; les personnalisations restent des préférences locales. L’icône Windows du paquet privé est la ressource originale locale déjà extraite.

Les chemins V_ sont décodés à partir du point local de tuile et des deltas signés ; S_ utilise l’origine globale et le contrôle de contour existant. Les données non reconnues ou tronquées restent intactes et ne sont pas interprétées. Les seuils d’apparition des catégories et légendes reprennent la classification native et les valeurs 200, 400 et 600 pixels par tuile. L’épaisseur des chemins et le mélange des transparences ne constituent pas une certification pixel par pixel de l’ancien moteur.

## Parcours utilisateur et limites explicites

L’installateur installe pour le compte Windows courant, propose le raccourci Bureau et le lancement, sans installer Python. Le premier lancement explique les commandes principales. La mise à jour et la désinstallation conservent les annotations et préférences hors du dossier du programme. Une identité de test distincte isole la recette d’installation.

Le moteur Python/Tk est indépendant du client Delphi historique. Les algorithmes opaques Bridge et lvl Wizard ne sont pas certifiés : les onglets correspondants proposent des aides explicites et conservent le texte brut. La génération MPQ historique n’est pas réimplémentée ; les cartes sont livrées préparées. Les protocoles anciens HTTP/FTP/MAPI, menus techniques masqués et commandes de publication automatiques ne sont pas réactivés. L’interface est alignée sur les fonctions documentées, sans revendication de copie binaire ou de parité intégrale de tous les algorithmes internes.

Les données 1.20 restent historiques ; Legacy est un candidat en lecture seule ; les annotations Forever sont historiques et recalées, sans nouvelle validation en jeu. Les droits de redistribution des cartes et bases tierces ne sont pas établis : le paquet avec données est destiné à l’usage local privé. Le code et les ressources tierces restent distincts.

## Vérification

Les journaux et manifestes de la livraison sous `outputs/ui-finalization-20261108/` documentent les tests automatisés, les contrôles visuels, les empreintes de build et la recette d’installation. Le bilan final de recette est fourni avec l’installateur.
