# MiMaMoo

מי מביא מה: רשימות משותפות לטיולים ולאירועים. אפליקציית דפדפן שאפשר להתקין למסך הבית.

## מבנה

- `index.html`, `sw.js`, `manifest.webmanifest`, `icons/`: האתר עצמו, כפי שהוא מוגש ב־GitHub Pages.
- `config.js`: החיבור ל־Firebase. כל עוד `firebase` הוא `null`, הנתונים נשמרים רק במכשיר.
- `tools/app-source.html`: קוד המקור של האפליקציה.
- `tools/build.py`: בונה את האתר מקוד המקור (`python3 tools/build.py tools/app-source.html <תיקיית-פלט> <גרסה>`).
- `tools/firestore.rules`: כללי הגישה למסד הנתונים ב־Firebase.
