# Visuels du portfolio

Sept images prêtes à être intégrées dans la case study. Chaque chiffre affiché
provient d'une exécution réelle du pipeline : aucune maquette, aucun nombre saisi
à la main.

Pour régénérer les visuels 01 à 04 :

    python src/make_portfolio_assets.py

English version: [README.md](README.md)

## Ce qui va dans le portfolio

| # | Image | Section du portfolio | Légende à utiliser |
|---|---|---|---|
| 00 | `00_workflow_diagram.png` | **Vue d'ensemble** | Des données brutes de terrain à une information géospatiale exploitable. |
| 01 | `01_raw_field_data.png` | **Le problème** | Les données de terrain arrivent avec des doublons, des valeurs manquantes, des dates impossibles et des géométries cassées. |
| 02 | `02_validation_rules.png` | **La démarche** | 22 règles explicites, 16 contrôles attributaires et 6 contrôles spatiaux, chacune traçable jusqu'à l'enregistrement concerné. |
| 03 | `03_pipeline_run.png` | **La démarche** | Une seule commande exécute tout le workflow et reproduit l'ensemble des sorties. |
| 04 | `04_quality_report.png` | **Les résultats** | 42 problèmes détectés sur 100 enregistrements, chacun rattaché à une règle et à un niveau de gravité. |
| 05 | `05_qgis_map.png` | **Validation SIG** | Parcelles validées, enregistrements à vérifier et chevauchements contrôlés dans QGIS. |
| 06 | `06_dashboard.png` | **Restitution** | Résultats du contrôle qualité résumés en indicateurs pour une lecture rapide. |

## Chiffres clés

Toutes les valeurs sont produites par le pipeline et stockées dans
`outputs/quality_report.csv`.

| Indicateur | Valeur |
|---|---:|
| Enregistrements synthétiques traités | **100** |
| Enregistrements validés | **63** |
| Enregistrements à vérifier | **31** |
| Enregistrements invalides | **6** |
| Problèmes détectés | **42** |
| Complétude des champs obligatoires | **98,7 %** |
| Problèmes spatiaux | **17** |
| Paires de parcelles qui se chevauchent | **3** |
| Erreurs injectées volontairement et retrouvées | **37 / 37** |

La dernière ligne est la plus forte : 37 erreurs ont été injectées volontairement
dans le jeu de données, et le pipeline les a toutes retrouvées. C'est l'argument à
mettre en avant.

## Texte de la case study

**Titre :** Field Data Quality & GIS Workflow
**Sous-titre :** Des données brutes de terrain à une information géospatiale validée

**Le problème**

Les équipes de terrain collectent de grands volumes de données géospatiales qui ne
peuvent pas servir à l'analyse ni au reporting tant qu'elles n'ont pas été
contrôlées. Identifiants dupliqués, coordonnées manquantes, dates impossibles,
surfaces incohérentes, géométries invalides et parcelles qui se chevauchent sont
fréquents, et invisibles tant que rien ne les cherche.

**La démarche**

J'ai conçu un workflow reproductible qui combine contrôles attributaires
automatisés, validation spatiale et revue SIG. Vingt-deux règles s'appliquent à
chaque enregistrement. Chaque règle produit un problème traçable assorti d'un
niveau de gravité, et chaque enregistrement reçoit un statut : `VALID`, `REVIEW`
ou `INVALID`. Le fichier brut n'est jamais modifié. Seuls les enregistrements qui
passent toutes les règles sont exportés comme données validées.

**Contrôle qualité automatisé**

Le workflow vérifie la complétude, l'unicité, la validité des coordonnées, la
cohérence entre attributs, la validité des géométries, l'appartenance à la zone
d'étude et les chevauchements. Pour vérifier le système lui-même, 37 erreurs ont
été injectées volontairement dans le jeu de données synthétiques : le pipeline les
a toutes redétectées.

**Validation SIG**

Les enregistrements valides sont exportés en GeoJSON prêt pour le SIG et revus
spatialement dans QGIS, aux côtés des enregistrements signalés et des surfaces de
chevauchement détectées.

**Restitution**

Les résultats du contrôle qualité sont résumés en indicateurs clés : taux de
validation, complétude, problèmes par type et par gravité. La qualité des données
se lit d'un coup d'œil et les enregistrements à corriger peuvent être renvoyés aux
équipes de terrain.

**Technologies**

Python, Pandas, GeoPandas, Shapely, Matplotlib, GeoJSON, QGIS

## Accès au code

> **Accès au code.** Le code source complet, les données et la documentation de
> ce projet sont publics :
> https://github.com/Estherbh/Field-Data-Quality-GIS-WORKFLOW

## Données et confidentialité

> **Note de confidentialité.** Ce projet de portfolio utilise 100 % de données non
> confidentielles. Le prototype repose entièrement sur des données synthétiques
> créées spécifiquement pour la démonstration. Aucune donnée confidentielle,
> propriétaire, opérationnelle ou non publiée d'une organisation n'est utilisée ni
> divulguée dans ce projet.
