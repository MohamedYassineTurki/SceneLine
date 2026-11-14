# La vidéo de présentation

**Fichier :** [`docs/media/SceneLine-presentation.mp4`](media/SceneLine-presentation.mp4) · 2 min 26 · 1920×1080 · en français.

La vidéo est elle-même **du code** : chaque scène est une page HTML animée avec GSAP, rendue image par image en
MP4 par [HyperFrames](https://hyperframes.heygen.com). Les sources sont dans [`motion-video/`](../motion-video).

## Structure

| Scène | Contenu |
|---|---|
| 1 · Témoignage | L'entretien de l'actrice Yasmine Dimassi (Nawaat), sous-titré en français |
| 2 · Constat | Une signature tardive bouscule toute la chaîne : annonceur, producteur, scénariste, acteurs |
| 3 · L'idée | SceneLine et les six angles d'**IA Éthique 360** |
| 4 · Démonstration | Les quatre étapes de l'application, avec les valeurs réelles du test sur « BALTRINGUE #1 » |
| 5 · Promesse | *L'IA propose. Le créateur décide. Le spectateur est informé.* |

## Comment elle est construite

| Élément | Outil |
|---|---|
| Composition et animation | HTML, CSS, GSAP, rendus en MP4 par HyperFrames |
| Voix off française | Gemini TTS (voix Puck), nettoyée par [`motion-video/tools/clean-vo.py`](../motion-video/tools/clean-vo.py) |
| Synchronisation | [`build-demo.mjs`](../motion-video/film/tools/build-demo.mjs) mesure chaque phrase enregistrée et fait apparaître chaque texte à l'écran **au moment exact où il est prononcé** |
| Effets sonores | ElevenLabs Sound Effects ; aucune musique |
| Typographie | Inter, fichiers locaux |

## Reconstruire la vidéo
```bash
cd motion-video/film
node tools/build-demo.mjs        # scènes de démonstration, calées sur la voix
python tools/build-index.py      # composition principale
npx hyperframes check            # vérifications : mise en page, contraste, animation
npx hyperframes render --fps 30 --quality delivery -o renders/SceneLine-video.mp4
```

Les extraits de l'entretien et de la série ne sont pas versionnés (droits) : voir [`motion-video/SOURCES.md`](../motion-video/SOURCES.md).
