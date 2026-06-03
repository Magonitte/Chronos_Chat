// One-off: align sidebar chat icons with Chronos branding (endpoint/spec/iconURL).
const result = db.conversations.updateMany(
  { endpoint: { $in: ['NewChat', 'Chronos'] } },
  {
    $set: {
      endpoint: 'Chronos',
      spec: 'chronos',
      iconURL: '/images/chronos.svg',
      modelLabel: 'Chronos',
    },
  },
);

print(`Updated ${result.modifiedCount} conversation(s).`);
printjson(
  db.conversations
    .find({}, { title: 1, endpoint: 1, spec: 1, iconURL: 1 })
    .sort({ updatedAt: -1 })
    .limit(5)
    .toArray(),
);
