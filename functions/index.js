/* MiMaMoo notifications (Cloud Functions 2nd gen, Tel Aviv, next to the database).
   When someone adds, takes or returns something in an event, the others in its group who switched
   notifications on get a message on their phones. The logic is in notify.js and lib.js. */
const {setGlobalOptions} = require('firebase-functions/v2');
const {onDocumentWrittenWithAuthContext, onDocumentWritten} = require('firebase-functions/v2/firestore');
const logger = require('firebase-functions/logger');
const {initializeApp} = require('firebase-admin/app');
const {getFirestore, FieldPath, FieldValue} = require('firebase-admin/firestore');
const {getMessaging} = require('firebase-admin/messaging');
const N = require('./notify');

initializeApp();
setGlobalOptions({region: 'me-west1', memory: '256MiB', maxInstances: 3, timeoutSeconds: 60});

const ctx = () => ({db: getFirestore(), messaging: getMessaging(), FieldPath, FieldValue});
const data = s => (s && s.exists ? s.data() : null);

const watch = col => onDocumentWrittenWithAuthContext('spaces/{space}/events/{eid}/' + col + '/{id}', async event => {
  const after = data(event.data && event.data.after);
  const r = await N.onChange(ctx(), {
    space: event.params.space, eid: event.params.eid, col,
    before: data(event.data && event.data.before), after,
    actor: event.authId || (after && after.by) || ''
  });
  if (!r.skip) logger.info(col + ' change', {sent: r.sent, failed: r.failed, removed: r.removed});
});

exports.itemNews = watch('items');
exports.dishNews = watch('dishes');

exports.pushTest = onDocumentWritten('users/{uid}/meta/pushtest', async event => {
  if (!data(event.data && event.data.after)) return;
  const r = await N.onTest(ctx(), event.params.uid);
  logger.info('test', {sent: r.sent, failed: r.failed, removed: r.removed});
});
