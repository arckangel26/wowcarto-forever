# Éditer les annotations de la carte

## Disponibilité

L’installation préparée de WoWCarto Forever démarre en **consultation seule**.
Dans ce parcours, la création, la modification et le partage d’annotations
sont désactivés. Le mode édition décrit ci-dessous existe dans le code pour un
profil où la consultation seule n’est pas activée ; il ne constitue pas une
fonction annoncée comme disponible dans l’installateur actuel. Un service de
contribution communautaire public opérationnel n’a pas été validé.

Pour signaler une erreur dès maintenant, ouvrez une issue sur le dépôt en
indiquant la base (FR ou EN), la région, le nom du point, l’erreur et, si
possible, la position correcte. Une capture sans données personnelles peut aider.

## Édition locale dans un environnement compatible

Sur un profil qui autorise l’édition, avec le jeu de données **1.20** :

1. Sélectionnez la langue de la base, puis activez **Mode édition** dans le menu.
   La **Base autorisée pour l’édition** doit correspondre à la base sélectionnée.
2. Pour créer un point, faites un clic droit sur la carte et choisissez
   **Ajouter une annotation**, ou utilisez `Ctrl+N` pour le centre de la carte.
3. Choisissez la catégorie et renseignez le nom, les niveaux, le commentaire et
   les propriétés nécessaires. `Ctrl+Entrée` enregistre ; Entrée ajoute une
   ligne dans le commentaire.
4. Pour modifier un point existant, faites un clic droit sur son marqueur et
   choisissez **Modifier l’annotation locale**. Les modifications restent
   locales et les données d’origine ne sont pas écrasées.
5. Utilisez **Sauvegarder le profil** pour conserver une copie de vos annotations
   et préférences dans un fichier `.wcfbackup`.

L’édition locale utilise des données 1.20 : elle ne valide pas automatiquement
les positions dans WoW Forever. Les données Legacy candidates sont en lecture
seule. Les commandes de partage présentes dans le code ne garantissent pas
qu’un service communautaire soit disponible ; elles exigent une action explicite.

Pour les commandes de navigation et les sauvegardes, consultez le
[guide Windows](CLIENT_WINDOWS.md). Pour contribuer au code ou signaler un
problème, consultez [Contribuer](../CONTRIBUTING.md).
