/* MiMaMoo: the Firebase connection (project mimamoo-b37c7, database in Tel Aviv).
   These values only name the project; who may read or change what is decided by the
   security rules (tools/firestore.rules), published in the Firebase console. */
window.MM_CONFIG = {
  firebase: {
    apiKey: "AIzaSyC0biC3ZmtpHLMDyax1LuYuLOFCuNJxtZA",
    authDomain: "mimamoo-b37c7.firebaseapp.com",
    projectId: "mimamoo-b37c7",
    storageBucket: "mimamoo-b37c7.firebasestorage.app",
    messagingSenderId: "136294577790",
    appId: "1:136294577790:web:5f3e7c4a58db74bc4b4a2f"
  },
  // Google sign-in (everything follows you to every device): true once Google is switched on in Firebase Authentication
  login: true,
  // the app's home is now Firebase Hosting; the old github.io address forwards people here with their data
  moveTo: "https://mimamoo-b37c7.firebaseapp.com/"
};
