# Guide QGIS : carte finale

Le code Python est terminé. La carte QGIS est la dernière preuve visuelle du workflow.

## 1. Créer et enregistrer le projet

1. Ouvre QGIS, crée un nouveau projet et laisse le SCR sur EPSG:4326 (WGS 84).
2. Enregistre-le sous qgis/field_data_quality.qgz.

## 2. Ajouter les trois couches

Utilise Couche → Ajouter une couche → Ajouter une couche vecteur, puis charge :

| Fichier | Rôle | Style conseillé |
|---|---|---|
| outputs/validated_data.geojson | Parcelles validées | Vert clair, contour vert foncé, opacité 45 %. |
| outputs/records_to_review.geojson | Parcelles à vérifier / invalides | Orange, contour rouge foncé, opacité 55 %. |
| outputs/spatial_overlaps.geojson | Zones de chevauchement | Magenta ou rouge, contour rouge, opacité 70 %. |

Si QGIS demande un système de coordonnées, sélectionne EPSG:4326 (WGS 84).

## 3. Étiquettes et lecture des problèmes

Active les étiquettes de records_to_review.geojson sur le champ record_id. Dans sa table attributaire, les champs issue_code, issue_description, severity et record_status expliquent chaque problème. Si la carte paraît chargée, n’étiquette que la couche de revue.

## 4. Mise en page à exporter

1. Va dans Projet → Nouvelle mise en page.
2. Ajoute la carte, le titre, une légende, une barre d’échelle et une flèche du nord.
3. Titre : Field Data Quality Control, Synthetic Dataset.
4. Sous-titre : Portfolio demonstration using synthetic data.
5. Ajoute en bas : 100% synthetic data, no confidential operational data.
6. Exporte le PNG sous docs/qgis_map_layout.png.

## 5. Check-list finale

- [ ] qgis/field_data_quality.qgz est enregistré.
- [ ] Les données validées, à revoir et les chevauchements ont des styles distincts.
- [ ] La mise en page comprend titre, légende, échelle et nord.
- [ ] La capture finale est docs/qgis_map_layout.png.
- [ ] Aucune donnée réelle ou confidentielle n’apparaît.


## Couche supplémentaire recommandée

Ajoute aussi data/synthetic/study_area.geojson. Place-la sous les autres couches avec un remplissage transparent et un contour gris foncé ou bleu foncé. Elle donne le contexte spatial sans masquer les parcelles.
