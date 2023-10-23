Intracursus Import
==================

## Installation

    $ git clone <...>
    $ cd <...>
    $ pip install -e .

## Utilisation

1. Télécharger sur Intracursus le fichier à compléter au format ***ODS*** (*XLS* non supporté).
2. Rajouter un onglet dans le fichier ODS, et y copier les noms des étudiants et les notes.
3. Lancer `import-scores <fichier.ods>`

Remarques:
* Il peut y avoir plusieurs colonnes de nombres (notes partielles par exemple), dans ce cas les notes doivent correspondre à la dernière colonne de nombres.
* Il peut y avoir une colonne prénom et une colonne nom, ou une seule colonne pour les deux
* La fusion peut également se baser sur les identifiants (INE), s'ils sont présents.