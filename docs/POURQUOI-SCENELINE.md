# Pourquoi SceneLine est différent

## Le problème
Dans l'audiovisuel, le placement de produit se négocie souvent **tard**, parfois à quelques jours du tournage.
Toute la chaîne en subit les effets : le producteur renégocie, le scénariste réécrit des scènes déjà validées,
les acteurs jouent un texte qui n'est plus le leur. L'actrice Yasmine Dimassi en témoigne dans un entretien
accordé à Nawaat, présenté au début de notre vidéo de présentation.

Les outils d'IA générative savent désormais **ajouter un objet dans un plan déjà tourné**. Cela pourrait libérer
le tournage de ces contrats de dernière minute. Mais utilisé sans garde-fou, le même outil peut :
- placer un produit dans une scène de deuil, de prière ou de fête traditionnelle ;
- imposer une marque étrangère dans un décor qui n'est pas le sien, et effacer la culture de l'œuvre ;
- modifier une œuvre sans l'accord de ses auteurs ;
- tromper le spectateur sur ce qui a été tourné et ce qui a été ajouté.

## Notre réponse
**SceneLine n'est pas un générateur de vidéo.** C'est une couche de **décision éthique** placée **avant**
et **après** la génération :

| | Outil de génération seul | **SceneLine** |
|---|---|---|
| Où placer le produit ? | L'utilisateur devine | Analyse de chaque scène, surfaces notées et vérifiées sur six images |
| Le contexte de la scène | Ignoré | Compris **avant** toute recherche : lieu, époque, ton, sensibilité |
| Scènes sacrées ou sensibles | Modifiables | **Protégées** : jamais envoyées à la recherche de surface |
| Produit hors contexte culturel | Accepté | **Cultural Integrity Guard** : écarté et expliqué |
| Qui décide ? | L'outil | **Le créateur**, décision signée et datée |
| Consentement | Implicite | **Explicite** à chaque envoi de données |
| Énergie | Générations d'essai | **Une génération par placement approuvé**, rien de plus |
| Synchronisation | Le plan généré dérive | **Recalage** sur le rythme du dialogue d'origine |
| Le spectateur | Non informé | **Étiquette** « Placement virtuel » + relevé des modifications |

## Ce qui rend la solution intelligente

### 1. Le modèle note, le code décide, l'humain tranche
Les modèles servent à **percevoir** (décrire une scène, noter une surface). Les **décisions** sont des règles
Python lisibles et testables (`classify()`, règles d'appariement, Guard). Le créateur a le dernier mot,
signé. Une hallucination du modèle devient au pire un « incertain », jamais une modification de l'œuvre.

### 2. Le contexte avant la surface
La plupart des approches cherchent d'abord une table vide. SceneLine comprend d'abord **ce que raconte la scène**.
Une scène de recueillement n'est même pas examinée : elle ne peut pas recevoir de produit, même par erreur.

### 3. La culture n'est pas une langue
Le Guard ne déduit **jamais** le pays de la langue parlée. Une série en français peut se passer à Tunis,
à Dakar ou à Paris. Le lieu est **déclaré par le producteur**, et chaque produit porte les marchés visés
par sa campagne. Sur une série française, une Badoit est proposée dans une cuisine parisienne ; une Boga Cidre,
marque tunisienne, y est écartée avec une explication. Sur une **série tunisienne**, avec les mêmes produits, c'est
l'inverse : la Boga est proposée dans le salon, la Badoit écartée partout. Et la darija des dialogues est transcrite
pour de vrai, pas réinventée en français.

### 3 bis. Rien n'est laissé au hasard de la génération
Un outil vidéo à qui l'on dit seulement « ajoute une canette » la rend trop grande, trop brillante, posée dans le
vide. SceneLine **mesure** la taille du produit à partir d'un objet voisin, l'**accorde** à la lumière et au grain de
la scène, et donne à l'outil une **image de référence** : la première image du plan, produit en place. Sur la série
tunisienne, c'est ce qui a fait passer la canette d'un objet collé, deux fois trop grand, à un accessoire du décor.

### 4. Respecter le montage et le jeu
Les intervalles suivent les **coupes** du montage, pour qu'un produit n'apparaisse pas au milieu d'un plan.
Le plan généré est **recalé image par image** sur l'original, pour que les gestes retombent sur le dialogue.
L'audio d'origine n'est jamais touché.

### 5. Sobre par conception
Le calcul lourd est local, le modèle léger gère les volumes, les résultats sont mis en cache, et la génération
vidéo, la plus coûteuse, n'a lieu qu'**à la demande**, pour un placement approuvé.

### 6. Tout est traçable
Chaque projet est un dossier de fichiers JSON relisibles. Chaque décision a une empreinte. Chaque version éditée
a un relevé qui dit **qui** a approuvé **quoi**, **quand**, et **avec quel outil** l'image a été produite.

## Pour qui
- **Producteurs et diffuseurs** : monétiser un catalogue existant sans retourner de scènes.
- **Scénaristes et réalisateurs** : protéger l'intention artistique, garder la main sur chaque modification.
- **Annonceurs** : apparaître là où leur produit a du sens, sans risque culturel pour leur marque.
- **Spectateurs** : savoir ce qui a été ajouté.
