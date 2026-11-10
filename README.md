<div align="center">

![WoWCarto Forever — cartographie communautaire](docs/assets/banner.svg)

# WoWCarto Forever

**La carte de votre aventure, à portée de clic.**

Un compagnon Windows inspiré de WoWCartographe 1.20 pour explorer les cartes de
WoW Forever et consulter les informations réunies par la communauté.

[Découvrir](#découvrir) · [Premiers pas](#premiers-pas) · [Éditer la carte](docs/EDITION.md) · [Remerciements](#remerciements) · [Contribuer](#contribuer)

`Windows 64 bits` &nbsp;·&nbsp; `FR / EN` &nbsp;·&nbsp; `Consultation hors ligne`

</div>

---

## Découvrir

**Une carte à explorer.** Déplacez-vous librement, zoomez, choisissez une région
et retrouvez les points d’intérêt sur une carte continue.

**Des informations à portée de recherche.** Cherchez un nom ou un commentaire,
filtrez les catégories et consultez les détails issus des bases historiques.

**Un esprit 1.20.** L’interface reprend l’organisation de WoWCartographe :
carte centrale, régions, liste, recherche, informations et marqueurs de difficulté.

**Vos cartes, sur votre ordinateur.** L’assistant lit votre installation locale
de WoW Forever et génère les cartes en qualité SD ou HD. Une connexion sert à
télécharger la base lors du premier démarrage ; la consultation reste ensuite
possible hors ligne.

## Premiers pas

1. Téléchargez et lancez l’installateur de la [préversion Windows 0.9.2](https://github.com/arckangel26/wowcarto-forever/releases/tag/v0.9.2-preview).
2. Au premier démarrage, sélectionnez le fichier `Wow.exe` de WoW Forever.
3. Choisissez **SD** ou **HD**, puis laissez l’application générer les cartes.
4. Choisissez la base **française** ou **anglaise**. Les informations sont
   téléchargées et vérifiées avant l’ouverture.
5. Explorez la carte en **consultation**.

L’installateur est non signé. Le parcours complet de cet installateur reste à vérifier.



## État du projet

Le projet est une **préversion en validation**. La génération SD, le téléchargement
de la base française, l’ouverture, la consultation et le redémarrage hors ligne
ont été vérifiés sur une installation Windows isolée avec WoW Forever
1.60.1.70862. La base anglaise et la génération HD ont également été testées,
mais pas toutes les combinaisons sur toutes les configurations.

Les bases FR et EN viennent de WoWCartographe 1.20. Leur contenu est historique :
la présence et la position de chaque annotation dans Forever ne sont pas toutes
vérifiées. Certaines informations peuvent donc avoir changé.

Le parcours d’installation décrit ci-dessus ouvre l’application en consultation.
L’édition locale peut ensuite être déverrouillée ; le service de contribution
communautaire public reste à valider.

## Éditer la carte

Vous souhaitez ajouter une annotation ou corriger une information ? Le
[guide d’édition](docs/EDITION.md) présente le déblocage par code et les limites
actuelles. Les modifications sont locales ; vous pouvez aussi signaler une erreur
dans une issue.

## Remerciements

Un grand merci à **Tixu**, créateur de WoWCartographe, pour son travail et pour
l’outil qui a inspiré ce projet. Son [site historique](http://tixu.scribe.free.fr/)
reste une référence précieuse de cette aventure.

Merci également à toutes les joueuses et à tous les joueurs de la communauté
originale qui ont partagé leurs découvertes et enrichi les cartes au fil des
années. WoWCarto Forever s’appuie sur ce patrimoine collectif.

## Contribuer

Un endroit incorrect, une recherche qui ne trouve pas ce qu’elle devrait, une idée
pour rendre la carte plus claire ? Une issue détaillant la version, la langue,
la zone et les étapes de reproduction aidera à avancer.

Les contributions au code sont bienvenues. Le [guide de contribution](CONTRIBUTING.md)
explique comment préparer une modification. Voir aussi le
[guide Windows](docs/CLIENT_WINDOWS.md) et les [précisions sur les ressources](NOTICE.md).

## Code et ressources

Le code original du projet est proposé sous [GPL-3.0](LICENSE). Les licences et droits
des dépendances et ressources tierces restent distincts ; consultez [NOTICE](NOTICE.md).
Les cartes du jeu et les bases `master.loc` ne sont pas incluses dans le dépôt.

WoWCarto Forever est un projet indépendant, sans affiliation officielle avec
Blizzard Entertainment ou les auteurs de WoWCartographe.
