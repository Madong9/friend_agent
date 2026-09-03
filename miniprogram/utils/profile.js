const UPDATE_FIELDS = [
  'nickname',
  'school',
  'campus',
  'grade',
  'major',
  'bio',
  'social_goals',
  'interests',
  'activities',
  'availability',
  'social_style',
  'avoidances',
  'recommendation_enabled',
];

function splitTags(value) {
  return String(value || '')
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildProfileUpdate(form, textFields) {
  const source = form || {};
  const payload = {};
  UPDATE_FIELDS.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(source, field)) {
      payload[field] = source[field];
    }
  });
  payload.interests = splitTags(textFields.interestsText);
  payload.social_goals = splitTags(textFields.goalsText);
  payload.activities = splitTags(textFields.activitiesText);
  payload.availability = splitTags(textFields.availabilityText);
  payload.avoidances = splitTags(textFields.avoidancesText);
  return payload;
}

module.exports = {
  UPDATE_FIELDS,
  splitTags,
  buildProfileUpdate,
};
