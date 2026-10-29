# MiMaMoo

מי מביא מה: רשימות משותפות לטיולים ולאירועים. אפליקציית דפדפן שאפשר להתקין למסך הבית.

## מבנה

- `index.html`, `sw.js`, `manifest.webmanifest`, `icons/`: האתר עצמו. הכתובת הראשית: https://mimamoo-b37c7.firebaseapp.com (מתפרסם אוטומטית מכל דחיפה, ראו `.github/workflows/firebase-hosting.yml` ו־`firebase.json`). הכתובת הישנה ב־GitHub Pages מעבירה לשם, עם הנתונים.
- `config.js`: החיבור ל־Firebase. כל עוד `firebase` הוא `null`, הנתונים נשמרים רק במכשיר. `login: true` מדליק התחברות עם Google; `moveTo` היא הכתובת שאליה GitHub Pages מעביר.
- `tools/app-source.html`: קוד המקור של האפליקציה.
- `tools/build.py`: בונה את האתר מקוד המקור (`python3 tools/build.py tools/app-source.html <תיקיית-פלט> <גרסה>`).
- `tools/firestore.rules`: כללי הגישה למסד הנתונים ב־Firebase.
