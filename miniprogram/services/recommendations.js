const STORAGE_KEY = 'latestRecommendations';

function getLatest() {
  return wx.getStorageSync(STORAGE_KEY) || [];
}

function setLatest(candidates) {
  const safeCandidates = Array.isArray(candidates) ? candidates : [];
  wx.setStorageSync(STORAGE_KEY, safeCandidates);
  return safeCandidates;
}

function removeCandidate(candidateId) {
  const remaining = getLatest().filter((item) => item.id !== candidateId);
  setLatest(remaining);
  return remaining;
}

module.exports = {
  STORAGE_KEY,
  getLatest,
  setLatest,
  removeCandidate,
};
